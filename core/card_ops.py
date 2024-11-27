import time
import win32file
import win32api
import win32com.client
import os
from .controller import ControllerType
from core.controller import SDController
from utils.logger import get_logger

logger = get_logger(__name__)

class CardInfo:
    def __init__(self):
        self.mode = None  # "8.0"/"7.0"/"4.0"/"3.0"
        self.controller_type = None
        self.device_path = None
        self.drive_letter = None
        self.capacity = 0  # 默认值为0
        self.name = None   # 添加卡名称属性
        
    def __str__(self):
        """返回卡信息的字符串表示"""
        try:
            if self.capacity is None or self.capacity == 0:
                capacity_str = "未知"
            else:
                capacity_str = f"{self.capacity/1024/1024/1024:.1f}GB"
            
            name_str = self.name if self.name else "未知"
            
            return f"SD卡 ({name_str}, 模式:{self.mode or '未知'}, " \
                   f"类型:{self.controller_type.value if self.controller_type else '未知'}, " \
                   f"容量:{capacity_str})"
        except Exception as e:
            logger.error(f"格式化卡信息时出错: {str(e)}", exc_info=True)
            return "SD卡信息格式化错误"

class CardOperations:
    def __init__(self):
        self.controller = SDController()
        self.timeout = 30  # 默认超时时间
        self._last_card_info = None  # 添加缓存
        
    def _get_device_path(self, drive_letter):
        """获取驱动器的设备路径"""
        try:
            # 使用WMI查询获取设备路径
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                for partition in disk.Associators_("Win32_DiskDriveToDiskPartition"):
                    for logical_disk in partition.Associators_("Win32_LogicalDiskToPartition"):
                        if logical_disk.DeviceID.lower() == drive_letter[0].lower() + ":":
                            logger.debug(f"找到设备路径: {disk.DeviceID} 对应驱动器: {drive_letter}")
                            return disk.DeviceID
            
            logger.warning(f"未找到驱动器 {drive_letter} 对应的设备路径")
            return None
            
        except Exception as e:
            logger.error(f"获取设备路径时出错: {str(e)}", exc_info=True)
            return None
    
    def check_card(self, full_check=False):
        """
        检查当前插入的SD卡状态
        full_check: 是否执行完整检测(包括性能测试)
        """
        try:
            # 检查所有可移动驱动器
            drives = self._get_removable_drives()
            for drive in drives:
                card_info = self._analyze_drive(drive, full_check)
                if card_info:
                    # 检查卡信息是否发生变化
                    if self._is_card_changed(card_info):
                        # 如果卡发生变化且需要完整检测
                        if not full_check:
                            # 执行完整检测以获取详细信息
                            detailed_info = self._analyze_drive(drive, True)
                            if detailed_info:
                                self._last_card_info = detailed_info
                                return detailed_info
                        else:
                            self._last_card_info = card_info
                    return self._last_card_info
        except Exception as e:
            logger.error(f"卡检测错误: {str(e)}", exc_info=True)
        return None
    
    def _is_card_changed(self, new_card_info):
        """检查卡信息是否发生变化"""
        if not self._last_card_info:
            return True
            
        # 比较关键属性
        return (new_card_info.device_path != self._last_card_info.device_path or
                new_card_info.drive_letter != self._last_card_info.drive_letter or
                new_card_info.name != self._last_card_info.name)
    
    def _analyze_drive(self, drive_letter, full_check=False):
        """分析驱动器类型和模式"""
        try:
            device_path = self._get_device_path(drive_letter)
            if not device_path:
                logger.warning(f"无法获取驱动器 {drive_letter} 的设备路径")
                return None
                
            # 获取WMI信息以进行基本分析
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                if disk.DeviceID == device_path:
                    # 检查是否为SD Express卡（NVMe模式）
                    if ("NVM" in disk.Model or 
                        "NVM" in disk.Caption or 
                        "NVMe" in disk.PNPDeviceID):
                        logger.info(f"检测到SD Express卡: {disk.Model}")
                        card_info = CardInfo()
                        card_info.name = disk.Model
                        card_info.drive_letter = drive_letter
                        card_info.device_path = device_path
                        card_info.controller_type = ControllerType.NVME
                        if full_check:
                            card_info.mode = self._determine_express_mode(device_path)
                            card_info.capacity = self._get_drive_capacity(drive_letter)
                        return card_info
                        
                    # 检查是否为传统SD卡（排除U盘）
                    elif disk.MediaType and "Removable Media" in disk.MediaType:
                        if ("USB" in disk.Model or 
                            "USB" in disk.Caption or 
                            "USB" in disk.Description):
                            logger.debug(f"跳过USB设备: {disk.Model}")
                            return None
                            
                        if ("SD" in disk.Model or 
                            "SD" in disk.Caption or 
                            "MMC" in disk.Model or 
                            "MMC" in disk.Caption or
                            "Card" in disk.Model or
                            "Card" in disk.Caption):
                            logger.info(f"检测到传统SD卡: {disk.Model}")
                            card_info = CardInfo()
                            card_info.name = disk.Model
                            card_info.drive_letter = drive_letter
                            card_info.device_path = device_path
                            card_info.controller_type = ControllerType.SD_HOST
                            if full_check:
                                card_info.mode = self._determine_sd_mode(device_path)
                                card_info.capacity = self._get_drive_capacity(drive_letter)
                            return card_info
                        else:
                            logger.debug(f"未识别为SD卡的可移动设备: {disk.Model}")
                            return None
            
            logger.debug(f"驱动器 {drive_letter} 不是SD卡设备")
            return None
            
        except Exception as e:
            logger.error(f"驱动器分析错误 {drive_letter}: {str(e)}", exc_info=True)
            return None
    
    def _determine_express_mode(self, device_path):
        """确定Express模式(7.0或8.0)"""
        try:
            # 使用WMI获取设备详细信息
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                if disk.DeviceID == device_path:
                    # 获取设备实例路径
                    pnp_id = disk.PNPDeviceID
                    
                    # 从设备管理器获取更多信息
                    for controller in wmi.InstancesOf("Win32_PnPEntity"):
                        if pnp_id in controller.PNPDeviceID:
                            # 检查设备属性和描述
                            desc = controller.Description.upper() if controller.Description else ""
                            name = controller.Name.upper() if controller.Name else ""
                            
                            logger.debug(f"SD Express卡设备信息: {desc} | {name}")
                            
                            # 检查传输速率来判断版本
                            if hasattr(controller, 'MaximumTransferRate'):
                                rate = float(controller.MaximumTransferRate)
                                if rate >= 2000:  # 2GB/s以上认为是8.0
                                    logger.info("检测到 SD Express 8.0 卡")
                                    return "8.0"
                                else:
                                    logger.info("检测到 SD Express 7.0 卡")
                                    return "7.0"
                            
                            # 如果无法获取速率，从描述中判断
                            if "PCIE GEN4" in desc or "GEN 4" in desc:
                                logger.info("根据PCIe版本检测到 SD Express 8.0 卡")
                                return "8.0"
                            elif "PCIE GEN3" in desc or "GEN 3" in desc:
                                logger.info("根据PCIe版本检测到 SD Express 7.0 卡")
                                return "7.0"
            
            # 如果无法确定具体版本，返回保守估计
            logger.warning("无法确定具体SD Express版本，默认返回7.0")
            return "7.0"
            
        except Exception as e:
            logger.error(f"SD Express模式检测失败: {str(e)}", exc_info=True)
            return "7.0"  # 出错时返回保守估计
    
    def _determine_sd_mode(self, device_path):
        """通过性能测试确定SD卡模式(4.0/3.0/2.0)"""
        try:
            perf_info = self._get_disk_performance(device_path)
            if not perf_info:
                logger.error("无法获取性能信息")
                return "3.0"  # 默认返回3.0
            
            max_speed = max(perf_info['read_speed'], perf_info['write_speed'])
            logger.debug(f"测得最大速度: {max_speed:.2f}MB/s")
            
            # UHS-II 速度范围：FD156是150MB/s，HD312是312MB/s
            if max_speed >= 150:  # UHS-II 最低速度阈值调整为 150MB/s
                logger.info(f"根据速度({max_speed:.2f}MB/s)判断为 SD 4.0 (UHS-II) 卡")
                return "4.0"
            # UHS-I 速度范围：SDR50是50MB/s，SDR104是104MB/s
            elif max_speed >= 30:  # UHS-I 速度范围在 30-104MB/s
                logger.info(f"根据速度({max_speed:.2f}MB/s)判断为 SD 3.0 (UHS-I) 卡")
                return "3.0"
            else:
                logger.info(f"根据速度({max_speed:.2f}MB/s)判断为 SD 2.0 卡")
                return "2.0"
                
        except Exception as e:
            logger.error(f"SD卡模式检测失败: {str(e)}", exc_info=True)
            return "3.0"  # 出错时返回较保守的估计
    
    def _get_disk_performance(self, device_path):
        """获取磁盘性能特征"""
        try:
            # 获取驱动器盘符
            drive_letter = None
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                if disk.DeviceID == device_path:
                    for partition in disk.Associators_("Win32_DiskDriveToDiskPartition"):
                        for logical_disk in partition.Associators_("Win32_LogicalDiskToPartition"):
                            drive_letter = logical_disk.DeviceID + "\\"
                            break
                    break
            
            if not drive_letter:
                logger.error("无法获取驱动器盘符")
                return None
            
            # 创建测试文件
            test_file = os.path.join(drive_letter, "speed_test.bin")
            test_size = 4 * 1024 * 1024  # 4MB
            block_size = 1024 * 1024  # 1MB
            
            try:
                # 写入测试
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
                
                data = os.urandom(test_size)
                start_time = time.time()
                
                for offset in range(0, len(data), block_size):
                    block = data[offset:offset + block_size]
                    win32file.WriteFile(handle, block)
                
                write_time = time.time() - start_time
                write_speed = test_size / write_time / (1024 * 1024)  # MB/s
                handle.Close()
                
                # 读取测试
                handle = win32file.CreateFile(
                    test_file,
                    win32file.GENERIC_READ,
                    0,  # 不共享
                    None,
                    win32file.OPEN_EXISTING,
                    win32file.FILE_FLAG_NO_BUFFERING | 
                    win32file.FILE_FLAG_SEQUENTIAL_SCAN,
                    None
                )
                
                start_time = time.time()
                bytes_read = 0
                
                while bytes_read < test_size:
                    win32file.ReadFile(handle, block_size)
                    bytes_read += block_size
                
                read_time = time.time() - start_time
                read_speed = test_size / read_time / (1024 * 1024)  # MB/s
                handle.Close()
                
                logger.debug(f"性能测试结果: 读取={read_speed:.1f}MB/s, 写入={write_speed:.1f}MB/s")
                
                return {
                    'read_speed': read_speed,
                    'write_speed': write_speed
                }
                
            finally:
                # 清理测试文件
                if os.path.exists(test_file):
                    try:
                        os.remove(test_file)
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"获取磁盘性能特征失败: {str(e)}", exc_info=True)
            return None
    
    def _get_drive_capacity(self, drive_letter):
        """获取驱动器容量"""
        try:
            # 使用GetDiskFreeSpaceEx获取总容量
            free_bytes, total_bytes, total_free_bytes = win32file.GetDiskFreeSpaceEx(drive_letter)
            logger.debug(f"驱动器 {drive_letter} 容量信息:")
            logger.debug(f"总容量: {total_bytes/1024/1024/1024:.1f}GB")
            logger.debug(f"可用空间: {free_bytes/1024/1024/1024:.1f}GB")
            return total_bytes
        except Exception as e:
            logger.error(f"获取驱动器容量时出错: {str(e)}", exc_info=True)
            
            # 尝试使用替代方法
            try:
                # 使用wmi查询获取容量
                wmi = win32com.client.GetObject("winmgmts:")
                for disk in wmi.InstancesOf("Win32_LogicalDisk"):
                    if disk.DeviceID.lower() == drive_letter[0].lower() + ":":
                        size = int(disk.Size)
                        logger.debug(f"通过WMI获取驱动器 {drive_letter} 容量: {size/1024/1024/1024:.1f}GB")
                        return size
            except Exception as e2:
                logger.error(f"WMI获取驱动器容量失败: {str(e2)}", exc_info=True)
            
            return 0
    
    def _get_removable_drives(self):
        """获取所有可能的SD卡驱动器（包括可移动驱动器和NVMe驱动器）"""
        try:
            drives = []
            bitmask = win32api.GetLogicalDrives()
            logger.debug(f"获取到驱动器位图: {bin(bitmask)}")
            
            # 使用WMI查询所有磁盘信息
            wmi = win32com.client.GetObject("winmgmts:")
            physical_disks = {disk.DeviceID: disk for disk in wmi.InstancesOf("Win32_DiskDrive")}
            
            for letter in range(26):
                if bitmask & (1 << letter):
                    drive_letter = f"{chr(65 + letter)}:\\"
                    drive_type = win32file.GetDriveType(drive_letter)
                    logger.debug(f"检查驱动器 {drive_letter}, 类型: {drive_type}")
                    
                    # 检查是否为可移动驱动器或NVMe驱动器
                    is_removable = (drive_type == win32file.DRIVE_REMOVABLE)
                    is_nvme = self._is_nvme_drive(drive_letter, physical_disks)
                    
                    if is_removable or is_nvme:
                        logger.debug(f"找到潜在的SD卡驱动器: {drive_letter} "
                                   f"({'可移动' if is_removable else 'NVMe'})")
                        drives.append(drive_letter)
            
            logger.info(f"扫描完成,找到驱动器: {drives}")
            return drives
            
        except Exception as e:
            logger.error(f"获取驱动器时出错: {str(e)}", exc_info=True)
            return []
            
    def _is_nvme_drive(self, drive_letter, physical_disks):
        """检查驱动器是否为NVMe设备"""
        try:
            # 获取驱动器对应的物理磁盘信息
            device_path = self._get_device_path(drive_letter)
            if not device_path:
                return False
                
            # 在物理磁盘列表中查找
            for disk in physical_disks.values():
                if disk.DeviceID == device_path:
                    # 检查是否为NVMe设备
                    is_nvme = ("NVM" in disk.Model or  # 检查型号
                              "NVM" in disk.Caption or  # 检查标题
                              "NVMe" in disk.PNPDeviceID)  # 检查PNP设备ID
                    
                    if is_nvme:
                        logger.debug(f"检测到NVMe驱动器: {drive_letter}")
                        logger.debug(f"设备信息: Model={disk.Model}, "
                                   f"Caption={disk.Caption}, "
                                   f"PNPDeviceID={disk.PNPDeviceID}")
                    return is_nvme
                    
            return False
            
        except Exception as e:
            logger.error(f"NVMe驱动器检查失败: {str(e)}", exc_info=True)
            return False