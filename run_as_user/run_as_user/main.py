import win32api
import win32con
import win32process
import win32security
import win32ts
import win32event
import win32pipe
import win32file
import threading
import sys
from contextlib import ExitStack

def get_current_user_token():
    """
    Gets the security token of the currently active user session.
    """
    sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
    for session in sessions:
        if session['State'] == win32ts.WTSActive:
            try:
                user_token = win32ts.WTSQueryUserToken(session['SessionId'])
                return user_token
            except Exception:
                continue
    raise Exception("No active user session found with a logged-on user.")

def run_as_current_user(command, log_file=None):
    """
    Runs a command as the currently logged-in user with real-time,
    interactive stdio forwarding.

    Args:
        command (str): The command to execute.
        log_file (str, optional): Path to a file for logging status messages.

    Returns:
        The exit code of the child process.
    """
    def log_message(message):
        if log_file:
            with open(log_file, "a") as f:
                f.write(f"[{threading.get_ident()}] {message}\n")

    with ExitStack() as stack:
        user_token = get_current_user_token()
        stack.callback(win32api.CloseHandle, user_token)

        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        
        # Create pipes for stdio
        stdin_read, stdin_write = win32pipe.CreatePipe(sa, 0)
        stdout_read, stdout_write = win32pipe.CreatePipe(sa, 0)
        stderr_read, stderr_write = win32pipe.CreatePipe(sa, 0)
        
        # Ensure handles are closed
        stack.callback(win32api.CloseHandle, stdin_read)
        stack.callback(win32api.CloseHandle, stdin_write)
        stack.callback(win32api.CloseHandle, stdout_read)
        stack.callback(win32api.CloseHandle, stdout_write)
        stack.callback(win32api.CloseHandle, stderr_read)
        stack.callback(win32api.CloseHandle, stderr_write)

        startup_info = win32process.STARTUPINFO()
        startup_info.dwFlags |= win32process.STARTF_USESTDHANDLES
        startup_info.hStdInput = stdin_read
        startup_info.hStdOutput = stdout_write
        startup_info.hStdError = stderr_write

        proc_handle, thread_handle, proc_id, thread_id = win32process.CreateProcessAsUser(
            user_token, None, command, None, None, True, 0, None, None, startup_info
        )
        stack.callback(win32api.CloseHandle, proc_handle)
        stack.callback(win32api.CloseHandle, thread_handle)

        log_message(f"Started process '{command}' with PID: {proc_id}")

        # Close handles not needed by the parent
        win32api.CloseHandle(stdin_read)
        win32api.CloseHandle(stdout_write)
        win32api.CloseHandle(stderr_write)

        def forward_stream(read_h, write_h, name):
            log_message(f"Starting forwarder thread for {name}")
            while True:
                try:
                    if name == "stdin": # Special handling for stdin
                        data = sys.stdin.buffer.read(1)
                        if not data: break
                    else:
                        hr, data = win32file.ReadFile(read_h, 4096)
                        if not data: break
                    
                    if name == "stdin":
                        win32file.WriteFile(write_h, data)
                    else:
                        write_h.buffer.write(data)
                        write_h.buffer.flush()
                except (IOError, BrokenPipeError, win32api.error):
                    break
            log_message(f"Forwarder thread for {name} finished.")
            if name == "stdin": win32api.CloseHandle(write_h)
            else: win32api.CloseHandle(read_h)

        # Create and start threads
        stdin_thread = threading.Thread(target=forward_stream, args=(None, stdin_write, "stdin"))
        stdout_thread = threading.Thread(target=forward_stream, args=(stdout_read, sys.stdout, "stdout"))
        stderr_thread = threading.Thread(target=forward_stream, args=(stderr_read, sys.stderr, "stderr"))
        
        stdin_thread.daemon = True # Allow main thread to exit even if this is blocked
        stdout_thread.start()
        stderr_thread.start()
        stdin_thread.start()

        log_message("Waiting for process to terminate...")
        win32event.WaitForSingleObject(proc_handle, win32event.INFINITE)
        exit_code = win32process.GetExitCodeProcess(proc_handle)
        log_message(f"Process terminated with exit code {exit_code}.")

        # Wait for output threads to finish
        stdout_thread.join()
        stderr_thread.join()
        
        return exit_code
