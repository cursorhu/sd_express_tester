import sys
import ctypes
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow
from cli.cli_runner import CLIRunner
from utils.logger import get_logger

# Get main logger
logger = get_logger()

def hide_console():
    """Hide console window"""
    kernel32 = ctypes.WinDLL('kernel32')
    user32 = ctypes.WinDLL('user32')
    get_win = kernel32.GetConsoleWindow
    show_win = user32.ShowWindow
    get_win.restype = ctypes.c_void_p
    handle = get_win()
    if handle:
        show_win(handle, 0)  # SW_HIDE = 0

def show_console():
    """Show console window"""
    kernel32 = ctypes.WinDLL('kernel32')
    user32 = ctypes.WinDLL('user32')
    get_win = kernel32.GetConsoleWindow
    show_win = user32.ShowWindow
    get_win.restype = ctypes.c_void_p
    handle = get_win()
    if handle:
        show_win(handle, 5)  # SW_SHOW = 5

def main():
    try:
        logger.info("Starting SD Express Tester")
        
        # Check for command line arguments
        is_cli = '--cli' in sys.argv
        
        if is_cli:
            # CLI mode: Show console
            show_console()
            logger.info("Running in CLI mode")
            cli = CLIRunner()
            cli.run()
        else:
            # GUI mode: Hide console
            hide_console()
            logger.info("Running in GUI mode")
            app = QApplication(sys.argv)
            window = MainWindow()
            window.show()
            sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Program error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 