from argparse import ArgumentParser, RawTextHelpFormatter, SUPPRESS
from pathlib import Path
from core.controller import SDController
from core.card_ops import CardOperations
from core.test_suite import TestSuite
from utils.logger import get_logger
from utils.config import config
from datetime import datetime

logger = get_logger(__name__)

class CLIRunner:
    def __init__(self):
        logger.debug("Initializing CLI runner")
        self.parser = ArgumentParser(
            description='SD Express Card Test Tool',
            add_help=False,  # Disable default help option
            formatter_class=RawTextHelpFormatter  # Keep help message format
        )
        self._setup_arguments()
        self.controller = SDController()
        self.card_ops = CardOperations(controller=self.controller)
        self.test_suite = TestSuite(self.card_ops)
        logger.debug("CLI runner initialization complete")
    
    def _setup_arguments(self):
        """Setup command line arguments"""
        # Add program description
        self.parser.usage = """
SDExpressTester [options]

Examples:
  ./SDExpressTester.exe --cli --run  # Run test according to config.yaml
"""
        
        basic = self.parser.add_argument_group('Basic Options')
        basic.add_argument('-h', '--help', 
                          action='help', 
                          default=SUPPRESS,
                          help='Show help message and exit')
        basic.add_argument('--cli',
                          action='store_true',
                          help='Run in command line mode')
        basic.add_argument('--run',
                          action='store_true',
                          help='Run test using config.yaml')
    
    def run(self):
        """Run CLI test"""
        try:
            args = self.parser.parse_args()
            logger.debug(f"CLI parameters: {args}")
            
            # Show help info when only --cli parameter is present
            if args.cli and not args.run:
                self.parser.print_help()
                return True
            
            # Execute test when both --cli and --run parameters are present
            if args.cli and args.run:
                logger.info("Starting CLI test")
            else:
                logger.info("Please use --cli and --run parameters to run test")
                return False
            
            # Check controller
            controller_info = self.controller._controller_info()
            # If SD Express is already in NVMe mode when running the tool, controller compatibility cannot be determined
            # So here we don't exit, just notify user
            if not controller_info:
                logger.info("SD controller may be incompatible or already in NVMe mode")
                print("INFO: SD controller may be incompatible or already in NVMe mode")
                # return False
            else:
                logger.info(f"Controller compatibility: {controller_info}")
                print(f"Controller compatibility: {controller_info}")
            
            # Wait and detect SD card
            print("Please insert SD card...")
            logger.info("Waiting for SD card insertion...")
            card_info = self.card_ops.wait_for_card(timeout=300)  # Use default timeout
            if not card_info:
                logger.error("No SD card detected or timeout")
                print("Error: No SD card detected or timeout")
                return False
                
            logger.info(f"SD card detected: {card_info}")
            print(f"SD card detected: {card_info}")
            
            # Get loop test configuration
            loop_enabled = config.get('test.loop.enabled', False)
            loop_count = config.get('test.loop.count', 1)
            
            # Use settings from config file
            test_config = {
                'mode': 'all',
                'type': 'quick',
                'timeout': 300,
                'config': config,  # Pass complete config object
                'progress_callback': self._update_progress,
                'result_callback': self._show_result,
                'status_callback': self._update_status
            }
            
            # Set output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"test_report_{timestamp}.txt")
            
            try:
                logger.info("Starting test...")
                # Initialize results list
                all_results = []

                # Execute loop test
                for i in range(loop_count if loop_enabled else 1):
                    if loop_enabled:
                        print(f"\n=== Test {i+1}/{loop_count} ===")
                        logger.info(f"Starting test {i+1}/{loop_count}")
                    
                    results = self.test_suite.run_tests(test_config)
                    if not results: break
                    all_results.append(results)
                
                # Generate report
                self._generate_report(all_results if loop_enabled else results, output_path)
                logger.info(f"Test report saved to: {output_path}")
                print(f"Test report saved to: {output_path}")
                
                logger.info("Test completed")
                return True
                
            except Exception as e:
                logger.error(f"Test process error: {str(e)}", exc_info=True)
                print(f"Error: Test process error: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"CLI run error: {str(e)}", exc_info=True)
            print(f"Error: {str(e)}")
            return False
    
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
                f.write("Test result:\n")
                self._write_test_details(f, all_results)

    def _write_test_details(self, f, results):
        """Write test details"""
        for test_name, result in results.items():
            status = "Passed" if result['passed'] else "Failed"
            f.write(f"\n{test_name}: {status}\n")
            details = result['details'].split('\n')
            for detail in details:
                if detail.strip():
                    f.write(f"  {detail}\n")

    def _update_progress(self, value):
        """Show progress"""
        print(f"\rProgress: {value}%", end="", flush=True)
        if value == 100:
            print()  # New line when complete
            
    def _show_result(self, result):
        """Show test results"""
        for test_name, test_result in result.items():
            status = "Passed" if test_result['passed'] else "Failed"
            print(f"{test_name}: {status}")
            print(f"Details: {test_result['details']}\n")
            
    def _update_status(self, message):
        """Update status"""
        print(f"\r{message}", end="\n", flush=True)