import os
import sys
from PyQt5.QtWidgets import (QMainWindow, QGroupBox, QLabel, QPushButton, 
                           QTextEdit, QVBoxLayout, QHBoxLayout, QWidget,
                           QProgressBar, QMessageBox, QApplication, QDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from core.controller import SDController
from core.card_ops import CardOperations
from core.test_suite import TestSuite
from utils.logger import get_logger
from utils.config import config
from datetime import datetime
from pathlib import Path

logger = get_logger(__name__)

# Add version info constants
VERSION = "1.0.5"
BUILD_DATE = "2025-01-06"
AUTHOR = "Thomas.Hu"
CONTACT = "thomas.hu@o2micro.com"

# Add About dialog class
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(400, 200)
        
        layout = QVBoxLayout()
        
        # Add icon
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdexpresstester.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(48, 48)
            icon_label.setPixmap(pixmap)
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
        
        # Add title
        title_label = QLabel("SD Express Tester")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Add version info
        version_label = QLabel(f"Version: {VERSION}\nRelease Date: {BUILD_DATE}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # Add author info
        author_label = QLabel(f"Author: {AUTHOR}\nEmail: {CONTACT}")
        author_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(author_label)

        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing main window")
        self.setWindowTitle("SD Express Tester")
        self.setMinimumSize(800, 600)
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdexpresstester.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logger.debug(f"Set window icon: {icon_path}")
        else:
            # Try to find icon in executable directory
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
            icon_path = os.path.join(exe_dir, 'sdexpresstester.ico')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.debug(f"Set window icon: {icon_path}")
            else:
                logger.warning(f"Icon file not found: {icon_path}")
        
        # Set window always on top
        always_on_top = config.get('ui.always_on_top', False)
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            logger.info("Window set to always on top")
        
        # Initialize UI
        self._setup_ui()
        
        # Delay initialize core components and check
        QTimer.singleShot(100, self._init_components)
    
    def _init_components(self):
        """Delay initialize core components"""
        try:
            self.controller = SDController()
            # Pass controller object to CardOperations, otherwise cannot update controller info through CardOperations
            # self.card_ops = CardOperations(controller=self.controller)
            
            sd_express_model = config.get('card.sd_express_model')
            if sd_express_model:
                self.card_ops = CardOperations(controller=self.controller, sd_express_model=sd_express_model)
                logger.info(f"Using specified SD Express model: {sd_express_model}")
            else:
                self.card_ops = CardOperations(controller=self.controller)
                logger.info("Using automatic logic to determine SD Express model")
                
            self.test_suite = TestSuite(self.card_ops)
            logger.info("Core components initialized")
            
            # Start check
            self._check_controller_status()
            self._check_card_status()
            
            # Add timer, check card status every second
            self.card_check_timer = QTimer()
            self.card_check_timer.timeout.connect(self._check_card_status)
            self.card_check_timer.start(1000)  # Check every 1000ms
            logger.debug("Started SD card status check timer")
            
        except Exception as e:
            logger.error(f"Failed to initialize core components: {str(e)}", exc_info=True)
            self.controller_info.setText("Controller status: Initialization failed")
            self.controller_info.setStyleSheet("color: red")
            self.test_btn.setEnabled(False)
    
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left main content area
        left_layout = QVBoxLayout()
        
        # Status panel
        self.status_panel = QGroupBox("System status")
        status_layout = QVBoxLayout()
        
        # Controller info (displayed in two lines)
        controller_layout = QVBoxLayout()
        self.controller_name = QLabel("Controller: Checking...")
        self.controller_capability = QLabel("Controller capability: Checking...")
        controller_layout.addWidget(self.controller_name)
        controller_layout.addWidget(self.controller_capability)
        
        # Card info (displayed in two lines)
        card_layout = QVBoxLayout()
        self.card_name = QLabel("SD: Waiting for insertion...")
        self.card_capability = QLabel("Card capability: Unknown")
        card_layout.addWidget(self.card_name)
        card_layout.addWidget(self.card_capability)
        
        status_layout.addLayout(controller_layout)
        status_layout.addLayout(card_layout)
        self.status_panel.setLayout(status_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Result display area
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        
        # Add to left layout
        left_layout.addWidget(self.status_panel)
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(self.result_text)
        
        # Right area
        right_layout = QVBoxLayout()
        
        # Icon display
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdexpresstester.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(128, 128)
            icon_label.setPixmap(pixmap)
            logger.debug(f"Added icon display: {icon_path}")
        else:
            # Try to find icon in executable directory
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
            icon_path = os.path.join(exe_dir, 'sdexpresstester.ico')
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                pixmap = icon.pixmap(128, 128)
                icon_label.setPixmap(pixmap)
                logger.debug(f"Added icon display: {icon_path}")
            else:
                logger.warning(f"Icon file not found: {icon_path}")
                icon_label.setText("Icon not found")
        
        icon_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(icon_label)
        
        # Test button
        test_btn_layout = QVBoxLayout()
        self.test_btn = QPushButton("Start test")
        self.test_btn.clicked.connect(self._start_test)
        self.stop_btn = QPushButton("Stop test")
        self.stop_btn.clicked.connect(self._stop_test)
        self.stop_btn.setEnabled(False)
        test_btn_layout.addWidget(self.test_btn)
        test_btn_layout.addWidget(self.stop_btn)
        
        # Tool button
        tools_btn_layout = QVBoxLayout()
        self.config_btn = QPushButton("Configuration file")
        self.config_btn.clicked.connect(self._open_config)
        self.log_btn = QPushButton("Log file")
        self.log_btn.clicked.connect(self._open_log)
        self.about_btn = QPushButton("About")  # Add About button
        self.about_btn.clicked.connect(self._show_about)
        tools_btn_layout.addWidget(self.config_btn)
        tools_btn_layout.addWidget(self.log_btn)
        tools_btn_layout.addWidget(self.about_btn)  # Add to layout
        
        # Add buttons to right layout
        right_layout.addLayout(test_btn_layout)
        right_layout.addSpacing(20)  # Add spacing
        right_layout.addLayout(tools_btn_layout)
        right_layout.addStretch()  # Add elastic space
        
        # Add left and right layouts to main layout
        main_layout.addLayout(left_layout, stretch=4)
        main_layout.addLayout(right_layout, stretch=1)
        
        # Add status bar
        self.statusBar = self.statusBar()
        self.statusBar.showMessage("Ready")

    def _check_controller_status(self):
        """Check SD controller status"""
        try:
            controller_info = self.controller._controller_info()
            if not controller_info:
                self.controller_name.setText("Controller: No supported controller detected")
                self.controller_name.setStyleSheet("color: red")
                self.controller_capability.setText("Controller capability: Unknown")
                self.controller_capability.setStyleSheet("color: red")
                self.test_btn.setEnabled(False)
                return
            
            # Update controller name and capability
            self.controller_name.setText(f"Controller: {controller_info['name']}")
            self.controller_name.setStyleSheet("color: green")
            self.controller_capability.setText(f"Controller capability: {', '.join(controller_info['capabilities'])}")
            self.controller_capability.setStyleSheet("color: green")
            
        except Exception as e:
            logger.error(f"Failed to check controller status: {str(e)}", exc_info=True)
            self.controller_name.setText("Controller: Check failed")
            self.controller_name.setStyleSheet("color: red")
            self.controller_capability.setText("Controller capability: Check failed")
            self.controller_capability.setStyleSheet("color: red")
            self.test_btn.setEnabled(False)

    def _check_card_status(self):
        """Check SD card status"""
        try:
            # Check SD card information
            card_info = self.card_ops.check_card()

            # Check controller information, there are two cases to check controller information
            # 1. The initial state has no inserted card, the controller is other NVMe SSDs on the platform.
            # 2. After inserting the SD card, the controller switches from NVMe SD Express to SD 4.0/3.0
            self._check_controller_status()

            if not card_info:
                self.card_name.setText("SD Card: Not Detected")
                self.card_name.setStyleSheet("color: red")
                self.card_capability.setText("Card Capability: Unknown")
                self.card_capability.setStyleSheet("color: red")
                self.test_btn.setEnabled(False)
                self.statusBar.showMessage("No SD card detected")
                return

            # Update card name and capability information
            self.card_name.setText(f"SD Card: {card_info.name}")
            self.card_name.setStyleSheet("color: green")
            
            # Build card capability information
            capability_info = []
            if card_info.mode:
                capability_info.append(f"Mode: {card_info.mode}")
            if card_info.capacity:
                capability_info.append(f"Capacity: {card_info.capacity/1024/1024/1024:.1f}GB")
            
            # Update card capability display
            self.card_capability.setText("Card Capability: " + ", ".join(capability_info))
            self.card_capability.setStyleSheet("color: green")

            # Enable test button
            self.test_btn.setEnabled(True)
            self.statusBar.showMessage("SD card ready")

        except Exception as e:
            logger.error(f"Failed to check SD card status: {str(e)}", exc_info=True)
            self.card_name.setText("SD card: Check failed")
            self.card_name.setStyleSheet("color: red")
            self.card_capability.setText("Card capability: Check failed")
            self.card_capability.setStyleSheet("color: red")
            self.test_btn.setEnabled(False)
 
    def _start_test(self):
        """Start test"""
        logger.info("Start test process")
        try:
            # Reset test suite status
            self.test_suite = TestSuite(self.card_ops)

            self.test_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.result_text.clear()
            
            # Add simple test start marker
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.result_text.insertHtml(
                f"=== Test start ({start_time}) ===<br><br>"
            )
            
            self.statusBar.showMessage("Executing test...")
            
            # Get loop test configuration
            loop_enabled = config.get('test.loop.enabled', False)
            loop_count = config.get('test.loop.count', 1)
            
            test_config = {
                'mode': 'all',
                'type': 'quick',
                'timeout': 300,
                'progress_callback': self._update_progress,
                'event_loop': QApplication.instance(),
                'result_callback': self._show_test_result,
                'config': config,  # Pass configuration object
                'status_callback': self._update_status  # Add status update callback
            }
            
            # Set output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"test_report_{timestamp}.txt")
            
            # Initialize result list
            all_results = []
            
            # Execute loop test
            for i in range(loop_count if loop_enabled else 1):
                if self.test_suite._stop_event.is_set():
                    logger.info("Test stopped by user, exit loop")
                    break
                
                if loop_enabled:
                    self.result_text.append(f"\n=== Test {i+1}/{loop_count} ===\n")
                    self.statusBar.showMessage(f"Executing test {i+1}/{loop_count}...")
                
                results = self.test_suite.run_tests(test_config)
                if not results:
                    break
                all_results.append(results)
            
            # Generate report
            self._generate_report(all_results if loop_enabled else results, output_path)
            logger.info(f"Test report saved to: {output_path}")
            self.statusBar.showMessage(f"Test report saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Test process error: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Test process error: {str(e)}")
            self.statusBar.showMessage("Test failed")

        finally:
            self._finish_test()
    
    def _stop_test(self):
        """Stop test"""
        logger.info("User requested to stop test")
        self.test_suite._stop_event.set()  # Set stop flag
        
        # Add stop information, but no summary
        self.result_text.insertHtml(
            "<br><span style='color: orange;'>Test stopped by user</span><br>"
        )
        
        self.statusBar.showMessage("Test stopped")
        self._finish_test()
    
    def _finish_test(self):
        """Finish test (whether normally or stopped)"""
        try:
            # Add test result summary
            summary_html = self._generate_test_summary()
            
            # Add simple test end marker
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.result_text.insertHtml(
                f"<br>=== Test end ({end_time}) ===<br>{summary_html}<br>"
            )
            
            self.test_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            
            # Scroll to bottom
            self.result_text.verticalScrollBar().setValue(
                self.result_text.verticalScrollBar().maximum()
            ) 
            
        except Exception as e:
            logger.error(f"Failed to update UI after test completion: {str(e)}", exc_info=True)
    
    def _generate_test_summary(self):
        """Generate test result summary"""
        try:
            text = self.result_text.toPlainText()
            if not text:
                return ""
            
            # Check if it's a loop test
            if "=== Test 1/" in text:
                # Loop test summary
                total_rounds = 0
                passed_rounds = 0
                failed_rounds = 0
                
                # Analyze each test round result
                rounds = text.split("=== Test ")[1:]
                for round_text in rounds:
                    if "/" not in round_text:
                        continue
                    
                    total_rounds += 1
                    test_items = 0
                    failed_items = 0
                    
                    # Check all test items in the current test round
                    lines = round_text.split('\n')
                    for line in lines:
                        if any(test in line for test in ["Controller Detection", "Basic Read/Write", "Performance Test", "Stability Test"]):
                            test_items += 1
                            if "Failed" in line or "Error" in line:  # Add check for "Error"
                                failed_items += 1
                    
                    # Only pass if all test items are completed and all passed
                    if test_items == 4 and failed_items == 0:
                        passed_rounds += 1
                    else:
                        failed_rounds += 1
                
                # Generate summary information
                if total_rounds == 0:
                    return "<br><span style='color: gray; font-weight: bold;'>Test result: No test completed</span>"
                else:
                    status_color = "green" if failed_rounds == 0 else "red"
                    return (f"<br><span style='color: {status_color}; font-weight: bold;'>"
                           f"Test result: Completed {total_rounds} rounds of testing, "
                           f"passed {passed_rounds} rounds, failed {failed_rounds} rounds</span>")
            else:
                # Single test summary logic remains unchanged
                test_items = 0
                failed_items = 0
                lines = text.split('\n')
                for line in lines:
                    if any(test in line for test in ["Controller Detection", "Basic Read/Write", "Performance Test", "Stability Test"]):
                        test_items += 1
                        if "Failed" in line:
                            failed_items += 1
                
                if test_items == 0:
                    return "<br><span style='color: gray; font-weight: bold;'>Test result: No test completed</span>"
                elif failed_items > 0:
                    return f"<br><span style='color: red; font-weight: bold;'>Test result: Test error (Failed items: {failed_items}/{test_items})</span>"
                elif test_items == 4:
                    return "<br><span style='color: green; font-weight: bold;'>Test result: Test passed</span>"
                else:
                    return "<br><span style='color: orange; font-weight: bold;'>Test result: Test not completed</span>"
            
        except Exception as e:
            logger.error(f"Failed to generate test summary: {str(e)}", exc_info=True)
            return "<br><span style='color: red; font-weight: bold;'>Test result: Summary failed</span>"
    
    def _update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
    
    def _update_status(self, message):
        """Update status bar"""
        self.statusBar.showMessage(message)
    
    def _show_test_result(self, result):
        """Display single test result"""
        for test_name, test_result in result.items():
            # Create simple HTML format text
            status = "Passed" if test_result['passed'] else "Failed"
            status_color = "green" if test_result['passed'] else "red"
            
            # Process detail text, convert newline characters to HTML line breaks
            details = test_result['details'].replace('\n', '<br>')
            
            # Use simple HTML format
            result_html = f"""
            <div>
                <span style='font-weight: bold;'>{test_name}: </span>
                <span style='color: {status_color};'>{status}</span><br>
                Details: {details}<br>
            </div>
            <br>
            """
            
            # Add HTML text to result display area
            self.result_text.insertHtml(result_html)
            
            # Update status bar
            status_msg = f"Test item {test_name}: {status}"
            self.statusBar.showMessage(status_msg)
            
            # Scroll to bottom
            self.result_text.verticalScrollBar().setValue(
                self.result_text.verticalScrollBar().maximum()
            )
    
    def _open_config(self):
        """Open configuration file"""
        try:
            config_path = config.get_config_path()
            if not config_path:
                QMessageBox.warning(self, "Error", "Configuration file not found")
                self.statusBar.showMessage("Error: Configuration file not found")
                return
                
            # Record the last modification time of the file
            self._last_config_mtime = os.path.getmtime(config_path)
            
            # Open configuration file
            os.startfile(config_path)
            self.statusBar.showMessage("Configuration file opened")
            
            # Start configuration file monitoring
            self._start_config_monitor()
            
        except Exception as e:
            logger.error(f"Failed to open configuration file: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open configuration file: {str(e)}")
            self.statusBar.showMessage("Error: Failed to open configuration file")
    
    def _start_config_monitor(self):
        """Start monitoring configuration file changes"""
        if not hasattr(self, 'config_monitor_timer'):
            self.config_monitor_timer = QTimer()
            self.config_monitor_timer.timeout.connect(self._check_config_changes)
            self.config_monitor_timer.start(1000)  # Check every second
    
    def _check_config_changes(self):
        """Check if the configuration file has changed"""
        try:
            config_path = config.get_config_path()
            if not config_path:
                return
                
            current_mtime = os.path.getmtime(config_path)
            if hasattr(self, '_last_config_mtime') and current_mtime > self._last_config_mtime:
                logger.info("Detected configuration file change, reload configuration")
                config.reload()
                self._last_config_mtime = current_mtime
                
                # Update window always on top status
                always_on_top = config.get('ui.always_on_top', False)
                flags = self.windowFlags()
                if always_on_top:
                    flags |= Qt.WindowStaysOnTopHint
                else:
                    flags &= ~Qt.WindowStaysOnTopHint
                self.setWindowFlags(flags)
                self.show()  # Need to redisplay the window
                
                self.statusBar.showMessage("Configuration file updated")
                
                # Stop monitoring timer
                if hasattr(self, 'config_monitor_timer'):
                    self.config_monitor_timer.stop()
                    delattr(self, 'config_monitor_timer')
                
        except Exception as e:
            logger.error(f"Failed to check configuration file changes: {str(e)}")
    
    def _open_log(self):
        """Open log file directory"""
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            if not os.path.exists(log_dir):
                # Try to find in executable directory
                log_dir = os.path.join(os.path.dirname(sys.executable), 'logs')
            
            if os.path.exists(log_dir):
                os.startfile(log_dir)
                self.statusBar.showMessage("Log directory opened")
            else:
                QMessageBox.warning(self, "Error", "Log directory not found")
                self.statusBar.showMessage("Error: Log directory not found")
        except Exception as e:
            logger.error(f"Failed to open log directory: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open log directory: {str(e)}")
            self.statusBar.showMessage("Error: Failed to open log directory")
    
    def _show_about(self):
        """Display About dialog"""
        dialog = AboutDialog(self)
        dialog.exec_()
    
    def _generate_report(self, all_results, output_path):
        """Generate test report"""
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write report header
            f.write("=== SD Express Tester Test Report ===\n")
            f.write(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Write configuration information
            f.write("Test configuration:\n")
            f.write(f"- Loop test: {'Enabled' if config.get('test.loop.enabled') else 'Disabled'}\n")
            if config.get('test.loop.enabled'):
                f.write(f"- Loop count: {config.get('test.loop.count')}\n")
            f.write(f"- Total size of performance test: {config.get('test.performance.total_size')}MB\n")
            f.write(f"- Performance test block size: {config.get('test.performance.block_size')}MB\n")
            f.write(f"- Performance test iterations: {config.get('test.performance.iterations')}\n\n")
            
            # Write test results
            if isinstance(all_results, list):  # Loop test results
                total_rounds = len(all_results)
                passed_rounds = sum(1 for results in all_results 
                                  if all(r.get('passed', False) for r in results.values()))
                failed_rounds = total_rounds - passed_rounds
                
                f.write(f"Test result summary:\n")
                f.write(f"- Total number of test rounds: {total_rounds}\n")
                f.write(f"- Passed rounds: {passed_rounds}\n")
                f.write(f"- Failed rounds: {failed_rounds}\n\n")
                
                # Write detailed results of each test round
                for round_num, results in enumerate(all_results, 1):
                    f.write(f"\n=== Test round {round_num}/{total_rounds} ===\n")
                    self._write_test_details(f, results)
                    
            else:  # Single test result
                f.write("Test results:\n")
                self._write_test_details(f, all_results)
    
    def _write_test_details(self, f, results):
        """Write test details"""
        for test_name, result in results.items():
            status = "Passed" if result['passed'] else "Failed"
            f.write(f"\n{test_name}: {status}\n")
            # Process multi-line details
            details = result['details'].split('\n')
            for detail in details:
                if detail.strip():
                    f.write(f"  {detail}\n")