import win32api
import win32con
import win32process
import win32security
import win32ts
import win32event
import win32pipe
import win32file
import threading
import os
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

def run_as_current_user(command, input_data=None, wait=True, log_file=None):
    """
    Runs a command as the currently logged-in user with full stdio redirection.

    Args:
        command (str): The command to execute.
        input_data (bytes, optional): Data to be sent to the process's stdin.
        wait (bool): Whether to wait for the command to complete.
        log_file (str, optional): Path to a file for logging status messages.

    Returns:
        A tuple (stdout_bytes, stderr_bytes) if wait is True, otherwise None.
    """
    def log_message(message):
        if log_file:
            with open(log_file, "a") as f:
                f.write(f"{message}\n")

    user_token = None
    
    with ExitStack() as stack:
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        
        stdin_read, stdin_write = win32pipe.CreatePipe(sa, 0)
        stack.callback(win32api.CloseHandle, stdin_read)
        stack.callback(win32api.CloseHandle, stdin_write)

        stdout_read, stdout_write = win32pipe.CreatePipe(sa, 0)
        stack.callback(win32api.CloseHandle, stdout_read)
        stack.callback(win32api.CloseHandle, stdout_write)

        stderr_read, stderr_write = win32pipe.CreatePipe(sa, 0)
        stack.callback(win32api.CloseHandle, stderr_read)
        stack.callback(win32api.CloseHandle, stderr_write)

        try:
            user_token = get_current_user_token()
            stack.callback(win32api.CloseHandle, user_token)
            
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

            log_message(f"Successfully started process '{command}' with PID: {proc_id}")

            # Child process now owns these handles, close them in the parent.
            win32api.CloseHandle(stdin_read)
            win32api.CloseHandle(stdout_write)
            win32api.CloseHandle(stderr_write)

            if input_data:
                win32file.WriteFile(stdin_write, input_data)
            win32api.CloseHandle(stdin_write)

            if not wait:
                return None, None

            stdout_chunks = []
            stderr_chunks = []

            def read_pipe(pipe, chunk_list):
                while True:
                    try:
                        hr, data = win32file.ReadFile(pipe, 4096)
                        if not data: break
                        chunk_list.append(data)
                    except win32api.error: break
                win32api.CloseHandle(pipe)

            stdout_thread = threading.Thread(target=read_pipe, args=(stdout_read, stdout_chunks))
            stderr_thread = threading.Thread(target=read_pipe, args=(stderr_read, stderr_chunks))

            stdout_thread.start()
            stderr_thread.start()

            log_message("Waiting for the process to complete...")
            win32event.WaitForSingleObject(proc_handle, win32event.INFINITE)
            
            stdout_thread.join()
            stderr_thread.join()
            
            log_message("Process completed.")

            return b"".join(stdout_chunks), b"".join(stderr_chunks)

        except Exception as e:
            log_message(f"An error occurred: {e}")
            if hasattr(e, 'winerror'):
                log_message(f"Win32 Error Code: {e.winerror}")
                log_message(f"Win32 Error Message: {win32api.FormatMessage(e.winerror)}")
            return None, None
