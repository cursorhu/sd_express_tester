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

logger = get_logger(__name__)

# 添加版本信息常量
VERSION = "1.0.0"
BUILD_DATE = "2024-11"
AUTHOR = "Thomas.Hu"
CONTACT = "thomas.hu@o2micro.com"

# 添加About对话框类
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(400, 200)
        
        layout = QVBoxLayout()
        
        # 添加图标
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdexpresstester.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(64, 64)
            icon_label.setPixmap(pixmap)
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
        
        # 添加标题
        title_label = QLabel("SD Express 测试工具")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 添加版本信息
        version_label = QLabel(f"版本: {VERSION}\n发布日期: {BUILD_DATE}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # 添加作者信息
        author_label = QLabel(f"作者: {AUTHOR}\n邮箱: {CONTACT}")
        author_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(author_label)

        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("初始化主窗口")
        self.setWindowTitle("SD Express 测试工具")
        self.setMinimumSize(800, 600)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdexpresstester.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logger.debug(f"设置窗口图标: {icon_path}")
        else:
            # 尝试在可执行文件目录查找图标
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
            icon_path = os.path.join(exe_dir, 'sdexpresstester.ico')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.debug(f"设置窗口图标: {icon_path}")
            else:
                logger.warning(f"图标文件不存在: {icon_path}")
        
        # 初始化UI
        self._setup_ui()
        
        # 延迟初始化核心组件和检测
        QTimer.singleShot(100, self._init_components)
        
        self._last_card_state = None
        self._full_check_required = False  # 新增标志
    
    def _init_components(self):
        """延迟初始化核心组件"""
        try:
            self.controller = SDController()
            self.card_ops = CardOperations()
            self.test_suite = TestSuite(self.card_ops)
            logger.info("核心组件初始化完成")
            
            # 开始检测
            self._check_controller()
            self._check_card_status()
            
            # 添加定时器,每秒检查一次卡状态
            self.card_check_timer = QTimer()
            self.card_check_timer.timeout.connect(self._check_card_status)
            self.card_check_timer.start(1000)  # 每1000ms检查一次
            logger.debug("已启动SD卡状态检查定时器")
            
        except Exception as e:
            logger.error(f"核心组件初始化失败: {str(e)}", exc_info=True)
            self.controller_info.setText("控制器状态: 初始化失败")
            self.controller_info.setStyleSheet("color: red")
            self.test_btn.setEnabled(False)
    
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧主要内容区域
        left_layout = QVBoxLayout()
        
        # 状态面板
        self.status_panel = QGroupBox("系统状态")
        status_layout = QVBoxLayout()
        
        # 控制器信息（分两行显示）
        controller_layout = QVBoxLayout()
        self.controller_name = QLabel("控制器: 检查中...")
        self.controller_capability = QLabel("控制器能力: 检查中...")
        controller_layout.addWidget(self.controller_name)
        controller_layout.addWidget(self.controller_capability)
        
        # 卡信息（分两行显示）
        card_layout = QVBoxLayout()
        self.card_name = QLabel("SD: 等待插入...")
        self.card_capability = QLabel("卡能力: 未知")
        card_layout.addWidget(self.card_name)
        card_layout.addWidget(self.card_capability)
        
        status_layout.addLayout(controller_layout)
        status_layout.addLayout(card_layout)
        self.status_panel.setLayout(status_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # 结果显示区
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        
        # 添加到左侧布局
        left_layout.addWidget(self.status_panel)
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(self.result_text)
        
        # 右侧区域
        right_layout = QVBoxLayout()
        
        # 图标显示
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdexpresstester.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(128, 128)
            icon_label.setPixmap(pixmap)
            logger.debug(f"添加图标显示: {icon_path}")
        else:
            # 尝试在可执行文件目录查找图标
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
            icon_path = os.path.join(exe_dir, 'sdexpresstester.ico')
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                pixmap = icon.pixmap(128, 128)
                icon_label.setPixmap(pixmap)
                logger.debug(f"添加图标显示: {icon_path}")
            else:
                logger.warning(f"图标文件不存在: {icon_path}")
                icon_label.setText("图标未找到")
        
        icon_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(icon_label)
        
        # 测试按钮
        test_btn_layout = QVBoxLayout()
        self.test_btn = QPushButton("开始测试")
        self.test_btn.clicked.connect(self._start_test)
        self.stop_btn = QPushButton("停止测试")
        self.stop_btn.clicked.connect(self._stop_test)
        self.stop_btn.setEnabled(False)
        test_btn_layout.addWidget(self.test_btn)
        test_btn_layout.addWidget(self.stop_btn)
        
        # 工具按钮
        tools_btn_layout = QVBoxLayout()
        self.config_btn = QPushButton("配置文件")
        self.config_btn.clicked.connect(self._open_config)
        self.log_btn = QPushButton("日志文件")
        self.log_btn.clicked.connect(self._open_log)
        self.about_btn = QPushButton("关于")  # 添加About按钮
        self.about_btn.clicked.connect(self._show_about)
        tools_btn_layout.addWidget(self.config_btn)
        tools_btn_layout.addWidget(self.log_btn)
        tools_btn_layout.addWidget(self.about_btn)  # 添加到布局
        
        # 添加按钮到右侧布局
        right_layout.addLayout(test_btn_layout)
        right_layout.addSpacing(20)  # 添加间距
        right_layout.addLayout(tools_btn_layout)
        right_layout.addStretch()  # 添加弹性空间
        
        # 将左右两侧布局添加到主布局
        main_layout.addLayout(left_layout, stretch=4)
        main_layout.addLayout(right_layout, stretch=1)
        
        # 添加状态栏
        self.statusBar = self.statusBar()
        self.statusBar.showMessage("就绪")
    
    def _check_controller(self):
        try:
            controller_info = self.controller.get_controller_info()
            if controller_info:
                # 显示控制器名称
                self.controller_name.setText(f"控制器: {controller_info['name']}")
                self.controller_name.setStyleSheet("color: green")
                
                # 显示控制器能力
                if controller_info['capabilities']:
                    self.controller_capability.setText(
                        f"控制器能力: {', '.join(controller_info['capabilities'])}")
                    self.controller_capability.setStyleSheet("color: green")
                    self.test_btn.setEnabled(True)
                else:
                    self.controller_capability.setText("控制器能力: 不支持")
                    self.controller_capability.setStyleSheet("color: red")
                    self.test_btn.setEnabled(False)
            else:
                self.controller_name.setText("控制器: 未检测到支持的控制器")
                self.controller_name.setStyleSheet("color: red")
                self.controller_capability.setText("控制器能力: 未知")
                self.controller_capability.setStyleSheet("color: red")
                self.test_btn.setEnabled(False)
                
        except Exception as e:
            logger.error(f"控制器检查失败: {str(e)}", exc_info=True)
            self.controller_name.setText("控制器: 检查失败")
            self.controller_name.setStyleSheet("color: red")
            self.controller_capability.setText("控制器能力: 检查失败")
            self.controller_capability.setStyleSheet("color: red")
            self.test_btn.setEnabled(False)
    
    def _check_card_status(self):
        """检查SD卡状态"""
        try:
            card_info = self.card_ops.check_card()  # 移除 quick_mode 参数
            
            # 更新卡名称显示
            if not card_info:
                self.card_name.setText("SD卡: 未检测到卡")
                self.card_name.setStyleSheet("color: red")
                self.card_capability.setText("卡能力: 未知")
                self.card_capability.setStyleSheet("color: red")
                self.test_btn.setEnabled(False)
                self.statusBar.showMessage("未检测到SD卡")
                return

            # 更新卡名称和能力信息
            self.card_name.setText(f"SD卡: {card_info.name or '未知'}")
            self.card_name.setStyleSheet("color: green")
            
            # 构建卡能力信息
            capability_info = []
            if card_info.mode:
                capability_info.append(f"模式: {card_info.mode}")
            if card_info.capacity:
                capability_info.append(f"容量: {card_info.capacity/1024/1024/1024:.1f}GB")
            
            # 更新卡能力显示
            self.card_capability.setText("卡能力: " + (", ".join(capability_info) if capability_info else "未知"))
            self.card_capability.setStyleSheet("color: green" if capability_info else "color: red")
            
            # 启用测试按钮
            self.test_btn.setEnabled(True)
            self.statusBar.showMessage("SD卡已就绪")

        except Exception as e:
            logger.error(f"SD卡状态检查失败: {str(e)}", exc_info=True)
            self.card_name.setText("SD卡: 检查失败")
            self.card_name.setStyleSheet("color: red")
            self.card_capability.setText("卡能力: 检查失败")
            self.card_capability.setStyleSheet("color: red")
            self.test_btn.setEnabled(False)
    
    def _perform_full_check(self):
        """执行完整的卡检测"""
        try:
            if not self._full_check_required:
                return
                
            card_info = self.card_ops.check_card(full_check=True)
            if card_info:
                self.card_name.setText(f"SD卡: {card_info.name}")
                self.card_name.setStyleSheet("color: green")
                
                capability_info = []
                if card_info.mode:
                    capability_info.append(f"模式: {card_info.mode}")
                if card_info.capacity:
                    capability_info.append(f"容量: {card_info.capacity/1024/1024/1024:.1f}GB")
                
                self.card_capability.setText("卡能力: " + ", ".join(capability_info))
                self.card_capability.setStyleSheet("color: green")
                self.test_btn.setEnabled(True)
                self.statusBar.showMessage("检测到SD卡插入")
            
            self._full_check_required = False
            
        except Exception as e:
            logger.error(f"完整卡检测失败: {str(e)}", exc_info=True)
    
    def _start_test(self):
        """开始测试"""
        logger.info("开始测试流程")
        try:
            self.test_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.result_text.clear()
            
            # 添加简单的测试开始标记
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.result_text.insertHtml(
                f"=== 测试开始 ({start_time}) ===<br><br>"
            )
            
            self.statusBar.showMessage("正在执行测试...")
            
            # 获取循环测试配置
            loop_enabled = config.get('test.loop.enabled', False)
            loop_count = config.get('test.loop.count', 1)
            
            test_config = {
                'mode': 'all',
                'type': 'quick',
                'timeout': 300,
                'progress_callback': self._update_progress,
                'event_loop': QApplication.instance(),
                'result_callback': self._show_test_result,
                'config': config,  # 传递配置对象
                'status_callback': self._update_status  # 添加状态更新回调
            }
            
            # 执行循环测试
            for i in range(loop_count if loop_enabled else 1):
                if self.test_suite._stop_event.is_set():  # 检查停止标志
                    logger.info("测试被用户停止，退出循环")
                    break
                
                if loop_enabled:
                    self.result_text.append(f"\n=== 第 {i+1}/{loop_count} 次测试 ===\n")
                    self.statusBar.showMessage(f"正在执行第 {i+1}/{loop_count} 次测试...")
                
                results = self.test_suite.run_tests(test_config)
                if not results or self.test_suite._stop_event.is_set():  # 检查测试结果和停止标志
                    break
            
            logger.info("测试完成")
            self.statusBar.showMessage("测试完成")
            
        except Exception as e:
            logger.error(f"测试过程出错: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "错误", f"测试过程出错: {str(e)}")
            self.statusBar.showMessage("测试失败")
        finally:
            self._finish_test()
    
    def _stop_test(self):
        """停止测试"""
        logger.info("用户请求停止测试")
        self.test_suite._stop_event.set()  # 设置停止标志
        
        # 添加停止信息，但不添加汇总
        self.result_text.insertHtml(
            "<br><span style='color: red;'>测试已被用户停止</span><br>"
        )
        
        self.statusBar.showMessage("测试已停止")
        self._finish_test()
    
    def _finish_test(self):
        """完成测试（无论是正常完成还是被停止）"""
        try:
            # 添加测试结果汇总
            summary_html = self._generate_test_summary()
            
            # 添加简单的测试结束标记
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.result_text.insertHtml(
                f"<br>=== 测试结束 ({end_time}) ===<br>{summary_html}<br>"
            )
            
            self.test_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            
            # 滚动到底部
            self.result_text.verticalScrollBar().setValue(
                self.result_text.verticalScrollBar().maximum()
            )
        except Exception as e:
            logger.error(f"完成测试更新UI失败: {str(e)}", exc_info=True)
    
    def _generate_test_summary(self):
        """生成测试结果汇总"""
        try:
            # 获取所有测试结果的文本
            text = self.result_text.toPlainText()
            
            # 检查是否被用户终止
            if "测试已被用户停止" in text:
                return "<br><span style='color: orange; font-weight: bold;'>测试结果: 测试终止</span>"
            
            # 检查是否是循环测试
            is_loop_test = "=== 第" in text
            
            if is_loop_test:
                # 统计每轮测试的结果
                rounds = text.split("=== 第")  # 分割每轮测试
                total_rounds = 0  # 总轮数
                passed_rounds = 0  # 通过的轮数
                failed_rounds = 0  # 失败的轮数
                
                for round_text in rounds:
                    if "测试项目" not in round_text:  # 跳过不包含测试结果的部分
                        continue
                        
                    total_rounds += 1
                    # 检查这一轮是否有失败的测试项
                    has_failed = False
                    test_items = 0  # 每轮的测试项数
                    lines = round_text.split('\n')
                    for line in lines:
                        if "测试项目" in line:
                            test_items += 1
                            if ": 失败" in line:
                                has_failed = True
                    
                    # 只有完成所有4个测试项才计入统计
                    if test_items == 4:
                        if has_failed:
                            failed_rounds += 1
                        else:
                            passed_rounds += 1
                    else:
                        total_rounds -= 1  # 未完成的轮次不计入总数
                
                # 生成循环测试汇总信息
                if total_rounds == 0:
                    return "<br><span style='color: gray; font-weight: bold;'>测试结果: 无测试完成</span>"
                elif failed_rounds > 0:
                    return (f"<br><span style='color: red; font-weight: bold;'>"
                           f"测试结果: 测试出错 (总计: {total_rounds}轮, 成功: {passed_rounds}轮, 失败: {failed_rounds}轮)"
                           f"</span>")
                else:
                    return (f"<br><span style='color: green; font-weight: bold;'>"
                           f"测试结果: 全部通过 (共 {total_rounds}轮)"
                           f"</span>")
            else:
                # 单次测试的汇总
                test_items = 0  # 测试项目总数
                failed_items = 0  # 失败的测试项数
                lines = text.split('\n')
                for line in lines:
                    if "测试项目" in line:
                        test_items += 1
                        if ": 失败" in line:
                            failed_items += 1
                
                if test_items == 0:
                    return "<br><span style='color: gray; font-weight: bold;'>测试结果: 无测试完成</span>"
                elif failed_items > 0:
                    return f"<br><span style='color: red; font-weight: bold;'>测试结果: 测试出错 (失败项: {failed_items}/{test_items})</span>"
                elif test_items == 4:  # 确保所有4个测试项都通过
                    return "<br><span style='color: green; font-weight: bold;'>测试结果: 测试通过</span>"
                else:
                    return "<br><span style='color: orange; font-weight: bold;'>测试结果: 测试未成</span>"
            
        except Exception as e:
            logger.error(f"生成测试汇总失败: {str(e)}", exc_info=True)
            return "<br><span style='color: red; font-weight: bold;'>测试结果: 汇总失败</span>"
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def _update_status(self, message):
        """更新状态栏"""
        self.statusBar.showMessage(message)
    
    def _show_test_result(self, result):
        """显示单个测试结果"""
        for test_name, test_result in result.items():
            # 创建简单的HTML格式文本
            status = "通过" if test_result['passed'] else "失败"
            status_color = "green" if test_result['passed'] else "red"
            
            # 处理详情文本，将换行符转换为HTML换行
            details = test_result['details'].replace('\n', '<br>')
            
            # 使用简单的HTML格式
            result_html = f"""
            <div>
                <span style='font-weight: bold;'>{test_name}: </span>
                <span style='color: {status_color};'>{status}</span><br>
                详情: {details}<br>
            </div>
            <br>
            """
            
            # 将HTML文本添加到结果显示区
            self.result_text.insertHtml(result_html)
            
            # 更新状态栏
            status_msg = f"测试项目 {test_name}: {status}"
            self.statusBar.showMessage(status_msg)
            
            # 滚动到底部
            self.result_text.verticalScrollBar().setValue(
                self.result_text.verticalScrollBar().maximum()
            )
    
    def _open_config(self):
        """打开配置文件"""
        try:
            config_path = config.get_config_path()
            if not config_path:
                QMessageBox.warning(self, "错误", "未找到配置文件")
                self.statusBar.showMessage("错误：未找到配置文件")
                return
                
            # 记录文件的最后修改时间
            self._last_config_mtime = os.path.getmtime(config_path)
            
            # 打开配置文件
            os.startfile(config_path)
            self.statusBar.showMessage("已打开配置文件")
            
            # 启动配置文件监控
            self._start_config_monitor()
            
        except Exception as e:
            logger.error(f"打开配置文件失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"打开配置文件失败: {str(e)}")
            self.statusBar.showMessage("错误：打开配置文件失败")
    
    def _start_config_monitor(self):
        """开始监控配置文件变化"""
        if not hasattr(self, 'config_monitor_timer'):
            self.config_monitor_timer = QTimer()
            self.config_monitor_timer.timeout.connect(self._check_config_changes)
            self.config_monitor_timer.start(1000)  # 每秒检查一次
    
    def _check_config_changes(self):
        """检查配置文件是否有变化"""
        try:
            config_path = config.get_config_path()
            if not config_path:
                return
                
            current_mtime = os.path.getmtime(config_path)
            if hasattr(self, '_last_config_mtime') and current_mtime > self._last_config_mtime:
                logger.info("检测到配置文件变化，重新加载配置")
                config.reload()
                self._last_config_mtime = current_mtime
                self.statusBar.showMessage("配置文件已更新")
                
                # 停止监控定时器
                if hasattr(self, 'config_monitor_timer'):
                    self.config_monitor_timer.stop()
                    delattr(self, 'config_monitor_timer')
                
        except Exception as e:
            logger.error(f"检查配置文件变化失败: {str(e)}")
    
    def _open_log(self):
        """打开日志文件目录"""
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            if not os.path.exists(log_dir):
                # 尝试在可执行文件目录查找
                log_dir = os.path.join(os.path.dirname(sys.executable), 'logs')
            
            if os.path.exists(log_dir):
                os.startfile(log_dir)
                self.statusBar.showMessage("已打开日志目录")
            else:
                QMessageBox.warning(self, "错误", "未找到日志目录")
                self.statusBar.showMessage("错误：未找到日志目录")
        except Exception as e:
            logger.error(f"打开日志目录失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"打开日志目录失败: {str(e)}")
            self.statusBar.showMessage("错误：打开日志目录失败")
    
    def _show_about(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec_()