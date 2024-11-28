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
        """设置测试用例"""
        self.test_cases = [
            TestCase("控制器检测", self._test_controller),
            TestCase("基本读写", self._test_basic_rw),
            TestCase("性能测试", self._test_performance),
            TestCase("稳定性测试", self._test_stability)
        ]
    
    def _get_test_path(self):
        """获取当前SD卡的测试路径"""
        card_info = self.card_ops.check_card()
        if not card_info:
            raise Exception("未检测到SD卡")
        return os.path.join(card_info.drive_letter, "test_files")
        
    def _show_test_details(self, test_name, details):
        """格式化测试详情"""
        if test_name == "控制器检测":
            return f"检测控制器类型和工作模式: {details}"
            
        elif test_name == "基本读写":
            return (f"执行基本读写测试:\n"
                   f"- 写入1MB随机数据\n"
                   f"- 读取并验证数据完整性\n"
                   f"结果: {details}")
            
        elif test_name == "性能测试":
            lines = details.split('\n')
            result = "执行性能测试:\n"
            for line in lines:
                if line:
                    size, speeds = line.split("测试", 1)
                    result += f"- {size}MB数据测试:\n"
                    result += f"  {speeds}\n"
            return result
            
        elif test_name == "稳定性测试":
            if "错误" in details:
                return f"执行稳定性测试:\n- 随机大小(512KB-2MB)读写测试\n{details}"
            else:
                return f"执行稳定性测试:\n- 随机大小(512KB-2MB)读写测试\n- {details}"
                
        return details

    def run_tests(self, config):
        """运行测试用例"""
        self._running = True
        self._stop_event.clear()
        results = {}
        
        # 更新状态
        if 'status_callback' in config:
            config['status_callback']("正在检查SD卡...")
        
        # 确保有SD卡
        card_info = self.card_ops.check_card()
        if not card_info:
            logger.error("未检测到SD卡，无法执行测试")
            result = {"错误": {"passed": False, "details": "未检测到SD卡"}}
            if 'result_callback' in config:
                config['result_callback'](result)
            return result
            
        logger.info(f"测试目标: {card_info}")
        
        # 创建测试目录
        test_dir = self._get_test_path()
        os.makedirs(test_dir, exist_ok=True)
        
        try:
            # 执行单轮测试
            total_tests = len(self.test_cases)
            for i, test_case in enumerate(self.test_cases):
                if self._stop_event.is_set():
                    logger.info("测试被手动停止")
                    break
                    
                try:
                    # 更新状态
                    if 'status_callback' in config:
                        config['status_callback'](f"正在执行测试: {test_case.name}")
                    # 处理界面事件循环，及时更新状态栏
                    if 'event_loop' in config:
                        config['event_loop'].processEvents()

                    logger.info(f"执行测试用例: {test_case.name}")
                    test_case.passed, test_case.details = test_case.func(config)
                    
                    # 更新进度
                    if 'progress_callback' in config:
                        progress = int((i + 1) * 100 / total_tests)
                        config['progress_callback'](progress)
                    
                    # 记录结果并实时显示
                    result = {
                        test_case.name: {
                            'passed': test_case.passed,
                            'details': test_case.details
                        }
                    }
                    results.update(result)
                    
                    # 调用结果回调
                    if 'result_callback' in config:
                        config['result_callback'](result)

                    logger.info(f"测试用例 {test_case.name} 完成: {'通过' if test_case.passed else '失败'}")                    
                    
                    # 处理界面事件循环，避免界面卡死
                    if 'event_loop' in config:
                        config['event_loop'].processEvents()

                except Exception as e:
                    logger.error(f"测试用例 {test_case.name} 执行出错: {str(e)}", exc_info=True)
                    result = {
                        test_case.name: {
                            'passed': False,
                            'details': f"测试异常: {str(e)}"
                        }
                    }
                    results.update(result)
                    if 'result_callback' in config:
                        config['result_callback'](result)
                        
        finally:
            # 清理测试文件
            try:
                if os.path.exists(test_dir):
                    for file in os.listdir(test_dir):
                        try:
                            os.remove(os.path.join(test_dir, file))
                        except Exception as e:
                            logger.error(f"清理测试文件失败: {str(e)}")
                    os.rmdir(test_dir)
            except Exception as e:
                logger.error(f"清理测试目录失败: {str(e)}")
        
        self._running = False
        return results
    
    def _test_performance(self, config):
        """性能测试"""
        try:
            # 从配置文件获参数
            total_size = config.get('test.performance.total_size', 128) * 1024 * 1024  # 转换为字节
            block_size = config.get('test.performance.block_size', 1) * 1024 * 1024
            iterations = config.get('test.performance.iterations', 3)
            
            results = []
            test_sizes = [total_size]
            
            # 获取测试路径
            test_dir = self._get_test_path()
            test_file = os.path.join(test_dir, "perf_test.bin")
            
            # 导入需要的Windows API
            import win32file
            
            for size in test_sizes:
                if self._stop_event.is_set():
                    return False, "测试被用户停止"
                    
                total_write_speed = 0
                total_read_speed = 0
                
                msg = f"开始 {size/1024/1024}MB 性能测试"
                logger.info(msg)
                
                for i in range(iterations):
                    if self._stop_event.is_set():
                        return False, "测试被用户停止"
                        
                    # 生成随机数
                    data = os.urandom(size)
                    
                    # 写速度测试
                    handle = None
                    try:
                        handle = win32file.CreateFile(
                            test_file,
                            win32file.GENERIC_WRITE,
                            0,  # 不共享
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
                    
                    # 等待一段时间确保数据写入
                    time.sleep(1)
                    
                    # 读速度测试
                    handle = None
                    try:
                        handle = win32file.CreateFile(
                            test_file,
                            win32file.GENERIC_READ,
                            0,  # 不共享
                            None,
                            win32file.OPEN_EXISTING,  # 使用OPEN_EXISTING而不是CREATE_ALWAYS
                            win32file.FILE_FLAG_NO_BUFFERING | 
                            win32file.FILE_FLAG_SEQUENTIAL_SCAN |
                            win32file.FILE_FLAG_OVERLAPPED,  # 启用异步I/O
                            None
                        )
                        
                        # 创建一个OVERLAPPED结构
                        overlapped = win32file.OVERLAPPED()
                        overlapped.Offset = 0
                        overlapped.OffsetHigh = 0
                        
                        buffer = win32file.AllocateReadBuffer(block_size)
                        bytes_read = 0
                        start_time = time.perf_counter()
                        
                        while bytes_read < size:
                            # 使用异步读取
                            result, _ = win32file.ReadFile(handle, buffer, overlapped)
                            if result == winerror.ERROR_IO_PENDING:
                                # 等待异步操作完成
                                win32file.GetOverlappedResult(handle, overlapped, True)
                            
                            overlapped.Offset += block_size  # 更新下一次读取的位置
                            bytes_read += block_size
                                
                        read_time = time.perf_counter() - start_time
                        read_speed = size / read_time / (1024 * 1024)
                        total_read_speed += read_speed
                        
                    finally:
                        if handle:
                            handle.Close()
                    
                    msg = f"第 {i+1} 次测试: 读取={read_speed:.2f}MB/s, 写入={write_speed:.2f}MB/s"
                    logger.debug(msg)
                    # 更新状态栏
                    if 'status_callback' in config:
                        config['status_callback'](msg)
                    if 'event_loop' in config:
                        config['event_loop'].processEvents()
                        
                # 计算平均速度
                avg_write_speed = total_write_speed / iterations
                avg_read_speed = total_read_speed / iterations
                
                results.append(f"{size/1024/1024}MB测试 (平均{iterations}次): "
                             f"读取速度={avg_read_speed:.2f}MB/s, "
                             f"写入速度={avg_write_speed:.2f}MB/s")
                
                logger.info(f"性能测试 {size/1024/1024}MB: "
                          f"读取={avg_read_speed:.2f}MB/s, "
                          f"写入={avg_write_speed:.2f}MB/s")
            
            return True, "\n".join(results)
            
        except Exception as e:
            logger.error(f"性能测试失败: {str(e)}", exc_info=True)
            return False, f"性能测试失败: {str(e)}"
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception as e:
                    logger.error(f"清理测试文件失败: {str(e)}")
    
    def _test_controller(self, config):
        """控制器测试"""
        try:
            logger.info("开始控制器测试")
            card_info = self.card_ops.check_card()
            if not card_info:
                return False, "未检测到SD卡"
                
            # 检查控制器类型和模式
            if card_info.controller_type == ControllerType.NVME:
                logger.info("检测到NVMe控制器")
                return True, f"NVMe控制器工作正常，模式: {card_info.mode}"
            elif card_info.controller_type == ControllerType.SD_HOST:
                logger.info("检测到SD Host控制器")
                return True, f"SD Host控制器工作正常，模式: {card_info.mode}"
            else:
                logger.warning("未知的控制器类型")
                return False, "未知的控制器类型"
                
        except Exception as e:
            logger.error(f"控制器测试失败: {str(e)}", exc_info=True)
            return False, f"控制器测试失败: {str(e)}"
            
    def _test_basic_rw(self, config):
        """基本读写测试"""
        try:
            test_dir = self._get_test_path()
            # 确保测试目录存在
            os.makedirs(test_dir, exist_ok=True)
            
            test_file = os.path.join(test_dir, "basic_rw_test.bin")
            test_size = 1 * 1024 * 1024  # 1MB
            
            logger.info(f"开始基本读写测试，文件大小: {test_size/1024/1024}MB")
            
            # 使用Windows API进行文件操作，以获得更好的控制
            try:
                # 写测试
                logger.debug("开始写入测试")
                data = os.urandom(test_size)
                
                handle = win32file.CreateFile(
                    test_file,
                    win32file.GENERIC_WRITE,
                    0,  # 不共享
                    None,
                    win32file.CREATE_ALWAYS,
                    win32file.FILE_FLAG_WRITE_THROUGH,
                    None
                )
                
                try:
                    win32file.WriteFile(handle, data)
                finally:
                    handle.Close()
                
                # 等待数据写入完成
                time.sleep(0.1)
                
                # 读测试
                logger.debug("开始读取测试")
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
                
                # 验证数据
                if data == read_data:
                    logger.info("基本读写测试通过")
                    return True, "读写测试成功，数据验证通过"
                else:
                    logger.error("数据验证失败")
                    return False, "数据验证失败"
                    
            except Exception as e:
                logger.error(f"文件操作失败: {str(e)}")
                return False, f"文件操作失败: {str(e)}"
                
        except Exception as e:
            logger.error(f"基本读写测试失败: {str(e)}", exc_info=True)
            return False, f"读写测试失败: {str(e)}"
            
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception as e:
                    logger.error(f"清理测试文件失败: {str(e)}")
    
    def _test_stability(self, config):
        """稳定性测试"""
        try:
            test_dir = self._get_test_path()
            iterations = 10 if config.get('type') == 'quick' else 100
            errors = 0
            
            logger.info(f"开始稳定性测试，迭代次数: {iterations}")
            
            for i in range(iterations):
                if self._stop_event.is_set():
                    logger.info("测试被手动停止")
                    return False, "测试被中断"
                    
                try:
                    # 随机读写测试
                    size = random.randint(512*1024, 2*1024*1024)  # 512KB到2MB
                    test_file = os.path.join(test_dir, f"stability_test_{i}.bin")
                    
                    logger.debug(f"第 {i+1}/{iterations} 次测试，文件大小: {size/1024:.1f}KB")
                    
                    # 写入测试
                    data = os.urandom(size)
                    with open(test_file, 'wb') as f:
                        f.write(data)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # 读取验证
                    with open(test_file, 'rb') as f:
                        read_data = f.read()
                    
                    if data != read_data:
                        logger.error(f"第 {i+1} 次测试数据验证失败")
                        errors += 1
                    
                    # 清理文件
                    os.remove(test_file)
                    
                except Exception as e:
                    logger.error(f"第 {i+1} 次测试失败: {str(e)}")
                    errors += 1
                
                # 更新进度
                if 'progress_callback' in config:
                    progress = int((i + 1) * 100 / iterations)
                    config['progress_callback'](progress)
            
            if errors == 0:
                logger.info("稳定性测试通过")
                return True, f"完成{iterations}次随机读写测试，无错误"
            else:
                logger.warning(f"稳定性测试完成，但有{errors}次错误")
                return False, f"测试完成，但有{errors}次错误"
                
        except Exception as e:
            logger.error(f"稳定性测试失败: {str(e)}", exc_info=True)
            return False, f"稳定性测试失败: {str(e)}"