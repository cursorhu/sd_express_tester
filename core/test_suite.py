import time
import os
import random
from threading import Event
from utils.logger import get_logger
from core.controller import ControllerType
import win32file
import winerror

logger = get_logger(__name__)

class TestCase:
    def __init__(self, name, func):
        self.name = name
        self.func = func
        self.passed = False
        self.details = ""

class TestSuite:
    def __init__(self, card_ops):
        self._running = False
        self._stop_event = Event()
        self.test_cases = []
        self.card_ops = card_ops
        self._setup_test_cases()
    
    def _setup_test_cases(self):
        """Setup test cases"""
        self.test_cases = [
            TestCase("Controller Detection", self._test_controller),
            TestCase("Basic Read/Write", self._test_basic_rw),
            TestCase("Performance Test", self._test_performance),
            TestCase("Stability Test", self._test_stability)
        ]
    
    def _get_test_path(self):
        """Get test path on current SD card"""
        card_info = self.card_ops.check_card()
        if not card_info:
            raise Exception("No SD card detected")
        return os.path.join(card_info.drive_letter, "test_files")
        
    def _show_test_details(self, test_name, details):
        """Format test details"""
        if test_name == "Controller Detection":
            return f"Detect controller type and working mode: {details}"
            
        elif test_name == "Basic Read/Write":
            return (f"Execute basic read/write test:\n"
                   f"- Write 1MB random data\n"
                   f"- Read and verify data integrity\n"
                   f"Result: {details}")
            
        elif test_name == "Performance Test":
            lines = details.split('\n')
            result = "Execute performance test:\n"
            for line in lines:
                if line:
                    size, speeds = line.split("test", 1)
                    result += f"- {size}MB data test:\n"
                    result += f"  {speeds}\n"
            return result
            
        elif test_name == "Stability Test":
            if "error" in details.lower():
                return f"Execute stability test:\n- Random size(512KB-2MB) read/write test\n{details}"
            else:
                return f"Execute stability test:\n- Random size(512KB-2MB) read/write test\n- {details}"
                
        return details

    def run_tests(self, config):
        """Run test cases"""
        self._running = True
        self._stop_event.clear()
        results = {}
        
        # Update status
        if 'status_callback' in config:
            config['status_callback']("Checking SD card...")
        
        # Ensure SD card exists
        card_info = self.card_ops.check_card()
        if not card_info:
            logger.error("No SD card detected, cannot execute tests")
            result = {"Error": {"passed": False, "details": "No SD card detected"}}
            if 'result_callback' in config:
                config['result_callback'](result)
            return result
            
        logger.info(f"Test target: {card_info}")
        
        # Create test directory
        test_dir = self._get_test_path()
        os.makedirs(test_dir, exist_ok=True)
        
        try:
            # Execute single round of tests
            total_tests = len(self.test_cases)
            for i, test_case in enumerate(self.test_cases):
                if self._stop_event.is_set():
                    logger.info("Test stopped manually")
                    break
                    
                try:
                    # Update status
                    if 'status_callback' in config:
                        config['status_callback'](f"Executing test: {test_case.name}")
                    # Handle UI event loop, update status bar in real time
                    if 'event_loop' in config:
                        config['event_loop'].processEvents()

                    logger.info(f"Executing test case: {test_case.name}")
                    test_case.passed, test_case.details = test_case.func(config)
                    
                    # Update progress
                    if 'progress_callback' in config:
                        progress = int((i + 1) * 100 / total_tests)
                        config['progress_callback'](progress)
                    
                    # Record results and display in real time
                    result = {
                        test_case.name: {
                            'passed': test_case.passed,
                            'details': test_case.details
                        }
                    }
                    results.update(result)
                    
                    # Call result callback
                    if 'result_callback' in config:
                        config['result_callback'](result)

                    logger.info(f"Test case {test_case.name} completed: {'Passed' if test_case.passed else 'Failed'}")                    
                    
                    # Handle UI event loop, avoid freezing the UI
                    if 'event_loop' in config:
                        config['event_loop'].processEvents()

                except Exception as e:
                    logger.error(f"Test case {test_case.name} execution error: {str(e)}", exc_info=True)
                    result = {
                        test_case.name: {
                            'passed': False,
                            'details': f"Test exception: {str(e)}"
                        }
                    }
                    results.update(result)
                    if 'result_callback' in config:
                        config['result_callback'](result)
                        
        finally:
            # Clean up test files
            try:
                if os.path.exists(test_dir):
                    for file in os.listdir(test_dir):
                        try:
                            os.remove(os.path.join(test_dir, file))
                        except Exception as e:
                            logger.error(f"Failed to clean up test files: {str(e)}")
                    os.rmdir(test_dir)
            except Exception as e:
                logger.error(f"Failed to clean up test directory: {str(e)}")
        
        self._running = False
        return results
    
    def _test_performance(self, config):
        """Performance test"""
        try:
            # Get parameters from configuration file
            total_size = config.get('test.performance.total_size', 128) * 1024 * 1024  # Convert to bytes
            block_size = config.get('test.performance.block_size', 1) * 1024 * 1024
            iterations = config.get('test.performance.iterations', 3)
            
            results = []
            test_sizes = [total_size]
            
            # Get test path
            test_dir = self._get_test_path()
            test_file = os.path.join(test_dir, "perf_test.bin")
            
            # Import needed Windows API
            import win32file
            
            for size in test_sizes:
                if self._stop_event.is_set():
                    return False, "Test stopped by user"
                    
                total_write_speed = 0
                total_read_speed = 0
                
                msg = f"Starting {size/1024/1024}MB performance test"
                logger.info(msg)
                
                for i in range(iterations):
                    if self._stop_event.is_set():
                        return False, "Test stopped by user"
                        
                    # Generate random data
                    data = os.urandom(size)
                    
                    # Write speed test
                    handle = None
                    try:
                        handle = win32file.CreateFile(
                            test_file,
                            win32file.GENERIC_WRITE,
                            0,  # Not shared
                            None,
                            win32file.CREATE_ALWAYS,
                            win32file.FILE_FLAG_NO_BUFFERING | 
                            win32file.FILE_FLAG_WRITE_THROUGH |
                            win32file.FILE_FLAG_SEQUENTIAL_SCAN,
                            None
                        )
                        
                        start_time = time.perf_counter()
                        for offset in range(0, len(data), block_size):
                            block = data[offset:offset + block_size]
                            win32file.WriteFile(handle, block)
                            
                        write_time = time.perf_counter() - start_time
                        write_speed = size / write_time / (1024 * 1024)
                        total_write_speed += write_speed
                        
                    finally:
                        if handle:
                            handle.Close()
                    
                    # Wait for a while to ensure data is written
                    time.sleep(1)
                    
                    # Read speed test
                    handle = None
                    try:
                        handle = win32file.CreateFile(
                            test_file,
                            win32file.GENERIC_READ,
                            0,  # Not shared
                            None,
                            win32file.OPEN_EXISTING,  # Use OPEN_EXISTING instead of CREATE_ALWAYS
                            win32file.FILE_FLAG_NO_BUFFERING | 
                            win32file.FILE_FLAG_SEQUENTIAL_SCAN |
                            win32file.FILE_FLAG_OVERLAPPED,  # Enable asynchronous I/O
                            None
                        )
                        
                        # Create an OVERLAPPED structure
                        overlapped = win32file.OVERLAPPED()
                        overlapped.Offset = 0
                        overlapped.OffsetHigh = 0
                        
                        buffer = win32file.AllocateReadBuffer(block_size)
                        bytes_read = 0
                        start_time = time.perf_counter()
                        
                        while bytes_read < size:
                            # Use asynchronous read
                            result, _ = win32file.ReadFile(handle, buffer, overlapped)
                            if result == winerror.ERROR_IO_PENDING:
                                # Wait for asynchronous operation to complete
                                win32file.GetOverlappedResult(handle, overlapped, True)
                            
                            overlapped.Offset += block_size  # Update the next read position
                            bytes_read += block_size
                                
                        read_time = time.perf_counter() - start_time
                        read_speed = size / read_time / (1024 * 1024)
                        total_read_speed += read_speed
                        
                    finally:
                        if handle:
                            handle.Close()
                    
                    msg = f"Test {i+1}: Read={read_speed:.2f}MB/s, Write={write_speed:.2f}MB/s"
                    logger.debug(msg)
                    # Update status bar
                    if 'status_callback' in config:
                        config['status_callback'](msg)
                    if 'event_loop' in config:
                        config['event_loop'].processEvents()
                        
                # Calculate average speed
                avg_write_speed = total_write_speed / iterations
                avg_read_speed = total_read_speed / iterations
                
                results.append(f"{size/1024/1024}MB test (Average {iterations} times): "
                             f"Read speed={avg_read_speed:.2f}MB/s, "
                             f"Write speed={avg_write_speed:.2f}MB/s")
                
                logger.info(f"Performance test {size/1024/1024}MB: "
                          f"Read={avg_read_speed:.2f}MB/s, "
                          f"Write={avg_write_speed:.2f}MB/s")
            
            return True, "\n".join(results)
            
        except Exception as e:
            logger.error(f"Performance test failed: {str(e)}", exc_info=True)
            return False, f"Performance test failed: {str(e)}"
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception as e:
                    logger.error(f"Failed to clean up test files: {str(e)}")
    
    def _test_controller(self, config):
        """Controller test"""
        try:
            logger.info("Starting controller test")
            card_info = self.card_ops.check_card()
            if not card_info:
                return False, "No SD card detected"
                
            # Check controller type and mode
            if card_info.controller_type == ControllerType.NVME:
                logger.info("Detected NVMe controller")
                return True, f"NVMe controller working normally, mode: {card_info.mode}"
            elif card_info.controller_type == ControllerType.SD_HOST:
                logger.info("Detected SD Host controller")
                return True, f"SD Host controller working normally, mode: {card_info.mode}"
            else:
                logger.warning("Unknown controller type")
                return False, "Unknown controller type"
                
        except Exception as e:
            logger.error(f"Controller test failed: {str(e)}", exc_info=True)
            return False, f"Controller test failed: {str(e)}"
            
    def _test_basic_rw(self, config):
        """Basic read/write test"""
        try:
            test_dir = self._get_test_path()
            # Ensure test directory exists
            os.makedirs(test_dir, exist_ok=True)
            
            test_file = os.path.join(test_dir, "basic_rw_test.bin")
            test_size = 1 * 1024 * 1024  # 1MB
            
            logger.info(f"Starting basic read/write test, file size: {test_size/1024/1024}MB")
            
            # Use Windows API for file operations to get better control
            try:
                # Write test
                logger.debug("Starting write test")
                data = os.urandom(test_size)
                
                handle = win32file.CreateFile(
                    test_file,
                    win32file.GENERIC_WRITE,
                    0,  # Not shared
                    None,
                    win32file.CREATE_ALWAYS,
                    win32file.FILE_FLAG_WRITE_THROUGH,
                    None
                )
                
                try:
                    win32file.WriteFile(handle, data)
                finally:
                    handle.Close()
                
                # Wait for data to finish writing
                time.sleep(0.1)
                
                # Read test
                logger.debug("Starting read test")
                handle = win32file.CreateFile(
                    test_file,
                    win32file.GENERIC_READ,
                    win32file.FILE_SHARE_READ,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None
                )
                
                try:
                    _, read_data = win32file.ReadFile(handle, test_size)
                finally:
                    handle.Close()
                
                # Verify data
                if data == read_data:
                    logger.info("Basic read/write test passed")
                    return True, "Read/write test successful, data verification passed"
                else:
                    logger.error("Data verification failed")
                    return False, "Data verification failed"
                    
            except Exception as e:
                logger.error(f"File operation failed: {str(e)}")
                return False, f"File operation failed: {str(e)}"
                
        except Exception as e:
            logger.error(f"Basic read/write test failed: {str(e)}", exc_info=True)
            return False, f"Read/write test failed: {str(e)}"
            
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception as e:
                    logger.error(f"Failed to clean up test files: {str(e)}")
    
    def _test_stability(self, config):
        """Stability test"""
        try:
            test_dir = self._get_test_path()
            iterations = 10 if config.get('type') == 'quick' else 100
            errors = 0
            
            logger.info(f"Starting stability test, iteration count: {iterations}")
            
            for i in range(iterations):
                if self._stop_event.is_set():
                    logger.info("Test stopped manually")
                    return False, "Test interrupted"
                    
                try:
                    # Random read/write test
                    size = random.randint(512*1024, 2*1024*1024)  # 512KB to 2MB
                    test_file = os.path.join(test_dir, f"stability_test_{i}.bin")
                    
                    logger.debug(f"Test {i+1}/{iterations}, file size: {size/1024:.1f}KB")
                    
                    # Write test
                    data = os.urandom(size)
                    with open(test_file, 'wb') as f:
                        f.write(data)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # Read and verify
                    with open(test_file, 'rb') as f:
                        read_data = f.read()
                    
                    if data != read_data:
                        logger.error(f"Data verification failed for test {i+1}")
                        errors += 1
                    
                    # Clean up file
                    os.remove(test_file)
                    
                except Exception as e:
                    logger.error(f"Test {i+1} failed: {str(e)}")
                    errors += 1
                
                # Update progress
                if 'progress_callback' in config:
                    progress = int((i + 1) * 100 / iterations)
                    config['progress_callback'](progress)
            
            if errors == 0:
                logger.info("Stability test passed")
                return True, f"Completed {iterations} random read/write tests, no errors"
            else:
                logger.warning(f"Stability test completed, but with {errors} errors")
                return False, f"Test completed, but with {errors} errors"
                
        except Exception as e:
            logger.error(f"Stability test failed: {str(e)}", exc_info=True)
            return False, f"Stability test failed: {str(e)}"