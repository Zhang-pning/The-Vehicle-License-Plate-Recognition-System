# 整合车牌检测和识别系统 - 完整修复版
import torch
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import yaml
import os
import sys
from pathlib import Path
import time

# ==================== 路径设置 ====================
# 获取当前脚本所在的目录
if getattr(sys, 'frozen', False):
    current_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))

# 切换到脚本所在目录
os.chdir(current_dir)
print(f"当前工作目录: {os.getcwd()}")
print(f"脚本所在目录: {current_dir}")

# 添加YOLOv5路径
yolov5_path = os.path.join(current_dir, 'yolov5')
if os.path.exists(yolov5_path):
    sys.path.insert(0, yolov5_path)
    print(f"已添加YOLOv5路径: {yolov5_path}")

# 添加当前目录到Python路径
sys.path.insert(0, current_dir)

# 修复YOLOv5导入
USE_BACKUP_DETECTOR = False
DetectMultiBackend = None
YOLO_UTILS = {}

try:
    # 尝试直接导入YOLOv5
    print("尝试导入YOLOv5模块...")

    # 添加必要的路径
    sys.path.insert(0, os.path.join(yolov5_path))
    sys.path.insert(0, os.path.join(yolov5_path, 'models'))
    sys.path.insert(0, os.path.join(yolov5_path, 'utils'))

    from models.common import DetectMultiBackend
    from utils.general import (
        check_img_size, non_max_suppression, scale_boxes,
        scale_segments, xyxy2xywh
    )
    from utils.plots import Annotator, colors
    from utils.segment.general import process_mask, process_mask_native

    # 保存引用
    YOLO_UTILS = {
        'check_img_size': check_img_size,
        'non_max_suppression': non_max_suppression,
        'scale_boxes': scale_boxes,
        'scale_segments': scale_segments,
        'xyxy2xywh': xyxy2xywh,
        'Annotator': Annotator,
        'colors': colors,
        'process_mask': process_mask,
        'process_mask_native': process_mask_native
    }

    print("成功导入YOLOv5模块")

except ImportError as e:
    print(f"导入YOLOv5模块失败: {e}")
    print("将使用备用检测方案")
    USE_BACKUP_DETECTOR = True

# 导入LPRNet
try:
    from models.LPRNet import LPRNet, CHARS

    print("成功导入LPRNet模块")
except ImportError as e:
    print(f"导入LPRNet模块失败: {e}")


def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    """调整图像尺寸并填充"""
    shape = im.shape[:2]  # 当前形状 [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # 缩放比例 (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # 只缩小，不放大
        r = min(r, 1.0)

    # 计算填充
    ratio = r, r  # 宽高比例
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh填充
    if auto:  # 最小矩形
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
    elif scaleFill:  # 拉伸
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]  # 宽高比例

    dw /= 2  # 分成两边填充
    dh /= 2

    if shape[::-1] != new_unpad:  # 调整大小
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # 添加边框
    return im, ratio, (dw, dh)


class LPRNetRecognizer:
    def __init__(self, weights_path, device):
        self.device = device
        self.lpr_max_len = 8
        self.class_num = len(CHARS)

        # 检查权重文件是否存在
        weights_abs = os.path.abspath(weights_path)
        if not os.path.exists(weights_abs):
            raise FileNotFoundError(f"LPRNet权重文件不存在: {weights_abs}")

        print("正在加载LPRNet模型...")

        # 创建模型
        self.model = LPRNet(lpr_max_len=self.lpr_max_len, phase=False,
                            class_num=self.class_num, dropout_rate=0)

        # 加载权重
        self.model.load_state_dict(torch.load(weights_abs, map_location=device))
        self.model.to(device)
        self.model.eval()

        print("LPRNet模型加载成功!")

    def preprocess_plate_for_lprnet(self, plate_image, mask=None):
        """专门为LPRNet预处理车牌图像"""
        try:
            # 如果有掩码，应用掩码
            if mask is not None:
                # 确保掩码与图像尺寸匹配
                if mask.shape[:2] != plate_image.shape[:2]:
                    mask = cv2.resize(mask, (plate_image.shape[1], plate_image.shape[0]))

                mask_binary = (mask > 0.5).astype(np.uint8)

                # 创建黑色背景
                processed_plate = np.zeros_like(plate_image)

                # 应用掩码
                for c in range(3):
                    processed_plate[:, :, c] = plate_image[:, :, c] * mask_binary
            else:
                processed_plate = plate_image

            # 调整到LPRNet输入尺寸 (94, 24)
            plate_resized = cv2.resize(processed_plate, (94, 24))

            # 转换为RGB
            plate_rgb = cv2.cvtColor(plate_resized, cv2.COLOR_BGR2RGB)

            # 归一化
            plate_normalized = plate_rgb.astype('float32')
            plate_normalized -= 127.5
            plate_normalized *= 0.0078125

            # 调整维度 [3, 24, 94]
            plate_tensor = np.transpose(plate_normalized, (2, 0, 1))
            plate_tensor = torch.from_numpy(plate_tensor).unsqueeze(0).to(self.device)

            return plate_tensor

        except Exception as e:
            print(f"车牌预处理错误: {e}")
            # 如果预处理失败，使用简单方法
            return self.preprocess_plate(plate_image)

    def preprocess_plate(self, plate_image):
        """原有的预处理方法（备用）"""
        # 调整到LPRNet输入尺寸 (94, 24)
        plate_resized = cv2.resize(plate_image, (94, 24))

        # 转换为RGB
        plate_rgb = cv2.cvtColor(plate_resized, cv2.COLOR_BGR2RGB)

        # 归一化
        plate_normalized = plate_rgb.astype('float32')
        plate_normalized -= 127.5
        plate_normalized *= 0.0078125

        # 调整维度 [3, 24, 94]
        plate_tensor = np.transpose(plate_normalized, (2, 0, 1))
        plate_tensor = torch.from_numpy(plate_tensor).unsqueeze(0).to(self.device)

        return plate_tensor

    def greedy_decode(self, preds):
        """贪心解码预测结果"""
        pred_labels = []
        preds = preds.cpu().detach().numpy()

        for i in range(preds.shape[0]):
            pred = preds[i, :, :]
            pred_label = []

            # 对每个时间步选择概率最大的字符
            for j in range(pred.shape[1]):
                pred_label.append(np.argmax(pred[:, j], axis=0))

            # 移除重复字符和空白字符
            no_repeat_blank_label = []
            pre_c = pred_label[0]
            if pre_c != len(CHARS) - 1:  # 如果不是空白字符
                no_repeat_blank_label.append(pre_c)

            for c in pred_label:
                if (pre_c == c) or (c == len(CHARS) - 1):
                    if c == len(CHARS) - 1:
                        pre_c = c
                    continue
                no_repeat_blank_label.append(c)
                pre_c = c

            pred_labels.append(no_repeat_blank_label)

        return pred_labels

    def recognize(self, plate_image):
        """识别车牌图像"""
        try:
            # 预处理
            plate_tensor = self.preprocess_plate(plate_image)

            # 推理
            with torch.no_grad():
                preds = self.model(plate_tensor)

            # 解码
            pred_labels = self.greedy_decode(preds)

            if pred_labels:
                plate_text = ''.join([CHARS[i] for i in pred_labels[0]])
                return plate_text
            else:
                return "识别失败"

        except Exception as e:
            print(f"车牌识别错误: {e}")
            return "识别错误"

    def recognize_with_mask(self, plate_image, mask=None):
        """使用掩码识别车牌图像"""
        try:
            # 预处理（使用掩码）
            plate_tensor = self.preprocess_plate_for_lprnet(plate_image, mask)

            # 推理
            with torch.no_grad():
                preds = self.model(plate_tensor)

            # 解码
            pred_labels = self.greedy_decode(preds)

            if pred_labels:
                plate_text = ''.join([CHARS[i] for i in pred_labels[0]])
                return plate_text
            else:
                return "识别失败"

        except Exception as e:
            print(f"车牌识别错误: {e}")
            return "识别错误"


class LicensePlateDetector:
    def __init__(self, weights_path, hyp_path, data_path):
        if USE_BACKUP_DETECTOR:
            self.use_backup = True
            self.names = ['blue', 'green', 'yellow']
            print("使用备用检测器")
            return

        # 检查文件是否存在
        weights_abs = os.path.abspath(weights_path)
        hyp_abs = os.path.abspath(hyp_path)
        data_abs = os.path.abspath(data_path)

        print(f"检查权重文件: {weights_abs}")
        print(f"检查超参数文件: {hyp_abs}")
        print(f"检查数据配置文件: {data_abs}")

        if not os.path.exists(weights_abs):
            raise FileNotFoundError(f"权重文件不存在: {weights_abs}")
        if not os.path.exists(hyp_abs):
            raise FileNotFoundError(f"超参数文件不存在: {hyp_abs}")
        if not os.path.exists(data_abs):
            raise FileNotFoundError(f"数据配置文件不存在: {data_abs}")

        print("正在加载YOLOv5模型...")

        # 加载设备
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"使用设备: {self.device}")
        self.use_backup = False

        try:
            # 加载模型
            self.model = DetectMultiBackend(weights_abs, device=self.device, dnn=False, data=data_abs, fp16=False)
            self.stride = self.model.stride
            self.names = self.model.names
            self.pt = self.model.pt

            # 加载超参数
            with open(hyp_abs, 'r', encoding='utf-8') as f:
                self.hyp = yaml.safe_load(f)

            # 加载数据配置
            with open(data_abs, 'r', encoding='utf-8') as f:
                self.data_cfg = yaml.safe_load(f)

            # 图像尺寸
            self.imgsz = YOLO_UTILS['check_img_size']((640, 640), s=self.stride)

            # 设置模型为评估模式
            self.model.eval()

            print(f"模型加载成功! 类别: {self.names}")

        except Exception as e:
            raise Exception(f"模型初始化失败: {e}")

    def preprocess_image(self, image_path):
        """预处理输入图像"""
        if self.use_backup:
            img0 = cv2.imread(image_path)
            return None, img0, img0

        # 读取图像
        img0 = cv2.imread(image_path)
        if img0 is None:
            raise ValueError(f"无法读取图像: {image_path}")

        # 保持原始图像副本
        original_img = img0.copy()

        # 调整图像尺寸
        img = letterbox(img0, self.imgsz, stride=self.stride, auto=self.pt)[0]

        # 转换颜色通道 BGR to RGB
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
        img = np.ascontiguousarray(img)

        # 转换为tensor
        img = torch.from_numpy(img).to(self.device)
        img = img.float() / 255.0  # 0 - 255 to 0.0 - 1.0
        if len(img.shape) == 3:
            img = img[None]  # 扩展为批处理

        return img, original_img, img0

    def detect(self, image_path, conf_thres=0.25, iou_thres=0.45):
        """执行检测"""
        if self.use_backup:
            # 备用检测逻辑
            img0 = cv2.imread(image_path)
            if img0 is None:
                return [], img0

            # 这里可以添加简单的检测逻辑
            # 现在返回空结果
            return [], img0

        # 预处理图像
        img, original_img, img0 = self.preprocess_image(image_path)

        # 推理
        with torch.no_grad():
            pred, proto = self.model(img, augment=False, visualize=False)[:2]

        # NMS
        pred = YOLO_UTILS['non_max_suppression'](pred, conf_thres, iou_thres,
                                                 classes=None, agnostic=False, max_det=1000, nm=32)

        results = []

        # 处理每个检测
        for i, det in enumerate(pred):
            if len(det):
                # 调整边界框到原始图像尺寸
                det[:, :4] = YOLO_UTILS['scale_boxes'](img.shape[2:], det[:, :4], img0.shape).round()

                # 处理掩码 - 使用YOLOv5官方方式
                masks = []
                if proto is not None:
                    # 使用process_mask_native处理掩码
                    masks = YOLO_UTILS['process_mask_native'](proto[i], det[:, 6:], det[:, :4], img0.shape[:2])

                # 提取结果
                for j, (*xyxy, conf, cls) in enumerate(reversed(det[:, :6])):
                    class_name = self.names[int(cls)]
                    confidence = float(conf)

                    # 获取掩码
                    mask = masks[j] if len(masks) > j else None

                    results.append({
                        'bbox': [int(x) for x in xyxy],
                        'class_name': class_name,
                        'confidence': confidence,
                        'mask': mask
                    })

        return results, original_img


def cv2ImgAddText(img, text, pos, textColor=(255, 0, 0), textSize=20):
    """在OpenCV图像上添加中文文本"""
    if (isinstance(img, np.ndarray)):
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    draw = ImageDraw.Draw(img)

    # 尝试加载字体文件
    font_path = os.path.join(current_dir, 'data', 'NotoSansCJK-Regular.ttc')
    if os.path.exists(font_path):
        try:
            fontText = ImageFont.truetype(font_path, textSize, encoding="utf-8")
        except:
            fontText = ImageFont.load_default()
            print("警告: 字体文件加载失败，使用默认字体")
    else:
        # 如果字体文件不存在，使用默认字体
        fontText = ImageFont.load_default()
        print("警告: 未找到中文字体文件，使用默认字体")

    draw.text(pos, text, textColor, font=fontText)
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


class LicensePlateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("车牌检测与识别系统")
        self.root.geometry("1200x700")

        # 初始化变量
        self.current_image = None
        self.detection_results = None
        self.original_image_path = None
        self.tk_image = None
        self.result_tk_image = None

        # 尝试初始化检测器和识别器
        self.detector = None
        self.recognizer = None
        self.initialize_models()

        self.setup_ui()

    def initialize_models(self):
        """初始化检测器和识别器"""
        try:
            # 检查必要的文件
            required_files = {
                'YOLOv5权重文件': 'weights/YOLOv5_weight/yolov5_best.pt',
                'LPRNet权重文件': 'weights/LPRNet_weight/lprnet_best.pth',
                '超参数文件': 'data/hyp.yaml',
                '数据配置': 'data/ccpd_datasets.yaml'
            }

            # 使用绝对路径检查
            missing_files = []
            for name, file in required_files.items():
                abs_path = os.path.abspath(file)
                if not os.path.exists(abs_path):
                    missing_files.append(f"{name}({abs_path})")
                else:
                    print(f"找到文件: {name} -> {abs_path}")

            if missing_files:
                raise FileNotFoundError(f"缺少必要文件: {', '.join(missing_files)}")

            # 初始化检测器
            self.detector = LicensePlateDetector(
                weights_path='weights/YOLOv5_weight/yolov5_best.pt',
                hyp_path='data/hyp.yaml',
                data_path='data/ccpd_datasets.yaml'
            )
            print("检测器加载成功!")

            # 初始化识别器
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.recognizer = LPRNetRecognizer(
                weights_path='weights/LPRNet_weight/lprnet_best.pth',
                device=device
            )
            print("LPRNet模型加载成功!")

        except Exception as e:
            print(f"模型加载失败: {e}")
            self.show_error_message(str(e))

    def show_error_message(self, message):
        """显示错误消息"""
        error_window = tk.Toplevel(self.root)
        error_window.title("错误")
        error_window.geometry("500x300")

        ttk.Label(error_window, text="初始化失败", font=("Arial", 14, "bold")).pack(pady=10)

        # 显示详细错误信息
        text_widget = tk.Text(error_window, wrap=tk.WORD, width=60, height=10)
        text_widget.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, message)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(error_window, text="确定", command=error_window.destroy).pack(pady=10)

    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # 按钮框架
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.load_btn = ttk.Button(btn_frame, text="选择图片", command=self.load_image)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.detect_btn = ttk.Button(btn_frame, text="开始检测识别", command=self.detect_and_recognize,
                                     state="normal" if self.detector and self.recognizer else "disabled")
        self.detect_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = ttk.Button(btn_frame, text="保存结果", command=self.save_result,
                                   state="disabled")
        self.save_btn.pack(side=tk.LEFT, padx=5)

        # 置信度阈值滑块
        threshold_frame = ttk.Frame(control_frame)
        threshold_frame.pack(fill=tk.X, pady=5)

        ttk.Label(threshold_frame, text="置信度阈值:").pack(side=tk.LEFT)
        self.conf_threshold = tk.DoubleVar(value=0.25)
        threshold_scale = ttk.Scale(threshold_frame, from_=0.1, to=1.0,
                                    variable=self.conf_threshold, orient=tk.HORIZONTAL)
        threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.threshold_label = ttk.Label(threshold_frame, text="0.25")
        self.threshold_label.pack(side=tk.RIGHT)

        threshold_scale.configure(command=self.update_threshold_label)

        # 结果显示区域
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True)

        # 原始图像
        original_frame = ttk.LabelFrame(display_frame, text="原始图像", padding=5)
        original_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.original_canvas = tk.Canvas(original_frame, bg='white', highlightthickness=1, highlightbackground="gray")
        self.original_canvas.pack(fill=tk.BOTH, expand=True)

        # 检测结果
        result_frame = ttk.LabelFrame(display_frame, text="检测识别结果", padding=5)
        result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.result_canvas = tk.Canvas(result_frame, bg='white', highlightthickness=1, highlightbackground="gray")
        self.result_canvas.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        status_text = "就绪" if self.detector and self.recognizer else "模型加载失败，请检查文件"
        self.status_var = tk.StringVar(value=status_text)
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def update_threshold_label(self, value):
        """更新阈值标签"""
        self.threshold_label.config(text=f"{float(value):.2f}")

    def load_image(self):
        """加载图像"""
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )

        if file_path:
            try:
                # 使用PIL打开图像
                image = Image.open(file_path)
                self.current_image = image
                self.original_image_path = file_path

                # 显示原始图像
                self.display_image(image, self.original_canvas)
                self.result_canvas.delete("all")
                self.result_canvas.create_text(100, 50, text="点击'开始检测识别'查看结果", fill="gray")

                self.save_btn.config(state="disabled")
                self.status_var.set(f"已加载图像: {os.path.basename(file_path)}")

            except Exception as e:
                self.status_var.set(f"加载图像失败: {e}")

    def display_image(self, image, canvas):
        """在画布上显示图像"""
        canvas.delete("all")

        # 获取画布尺寸
        canvas.update()
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()

        if canvas_width <= 1:
            canvas_width = 500
        if canvas_height <= 1:
            canvas_height = 400

        # 计算缩放比例
        img_width, img_height = image.size
        scale = min(canvas_width / img_width, canvas_height / img_height) * 0.95  # 留一些边距
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        # 调整图像大小
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        tk_image = ImageTk.PhotoImage(resized_image)

        # 在画布中心显示图像
        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        canvas.create_image(x, y, anchor=tk.NW, image=tk_image)

        # 保存引用防止垃圾回收
        if canvas == self.original_canvas:
            self.tk_image = tk_image
        else:
            self.result_tk_image = tk_image

        return scale, (x, y)

    def detect_and_recognize(self):
        """执行检测和识别"""
        if not self.detector or not self.recognizer:
            self.status_var.set("模型未初始化!")
            return

        if not hasattr(self, 'original_image_path') or not self.original_image_path:
            self.status_var.set("请先选择图像!")
            return

        try:
            self.status_var.set("正在检测和识别...")
            self.root.update()

            # 执行检测
            results, original_img = self.detector.detect(
                self.original_image_path,
                conf_thres=self.conf_threshold.get()
            )

            self.detection_results = results

            # 创建带检测结果的图像
            result_img = original_img.copy()

            # 为每个检测结果绘制边界框、掩码和识别结果
            for i, result in enumerate(results):
                bbox = result['bbox']
                class_name = result['class_name']
                confidence = result['confidence']
                mask = result['mask']

                # 根据类别选择边界框颜色
                if class_name == 'blue':
                    bbox_color = (255, 0, 0)  # 蓝色 (BGR)
                    color_name = "蓝色"
                elif class_name == 'green':
                    bbox_color = (0, 255, 0)  # 绿色
                    color_name = "绿色"
                else:  # yellow
                    bbox_color = (0, 255, 255)  # 黄色
                    color_name = "黄色"

                # 绘制分割掩码
                if mask is not None:
                    try:
                        if hasattr(mask, 'cpu'):
                            mask_np = mask.cpu().numpy()
                        else:
                            mask_np = mask

                        mask_binary = (mask_np > 0.5).astype(np.uint8)

                        # 创建淡红色覆盖层
                        overlay = result_img.copy()
                        overlay[mask_binary > 0] = [50, 50, 200]  # 淡红色 (BGR)
                        result_img = cv2.addWeighted(overlay, 0.4, result_img, 0.6, 0)

                    except Exception as mask_error:
                        print(f"掩码处理错误: {mask_error}")

                # 裁剪车牌区域进行识别 - 修复版本
                x1, y1, x2, y2 = bbox
                plate_region = original_img[y1:y2, x1:x2].copy()

                # 识别车牌号码
                plate_number = "识别中..."
                if plate_region.size > 0:
                    # 获取对应的掩码区域
                    mask_region = None
                    if mask is not None:
                        try:
                            if hasattr(mask, 'cpu'):
                                mask_np = mask.cpu().numpy()
                            else:
                                mask_np = mask
                            mask_region = mask_np[y1:y2, x1:x2]
                        except Exception as e:
                            print(f"获取掩码区域错误: {e}")

                    # 使用改进的识别方法
                    plate_number = self.recognizer.recognize_with_mask(plate_region, mask_region)

                    # 打印调试信息
                    print(f"车牌区域尺寸: {plate_region.shape}")
                    if mask_region is not None:
                        print(f"掩码区域尺寸: {mask_region.shape}")

                # 绘制边界框
                cv2.rectangle(result_img, (x1, y1), (x2, y2), bbox_color, 2)

                # 准备显示文本
                display_text = f"{color_name} {plate_number}"

                # 使用支持中文的函数绘制文本
                text_pos = (x1, max(y1 - 30, 30))
                result_img = cv2ImgAddText(result_img, display_text, text_pos, (255, 255, 255), 16)

                # 在文本下方绘制一个小背景
                text_bg_y = text_pos[1] + 20
                cv2.rectangle(result_img, (x1, text_bg_y - 15), (x1 + 120, text_bg_y), bbox_color, -1)
                confidence_text = f"置信度: {confidence:.2f}"
                result_img = cv2ImgAddText(result_img, confidence_text, (x1, text_bg_y - 15), (255, 255, 255), 12)

            # 转换BGR到RGB
            result_img_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
            result_pil = Image.fromarray(result_img_rgb)

            # 显示结果
            self.display_image(result_pil, self.result_canvas)

            # 启用保存按钮
            self.save_btn.config(state="normal")

            self.status_var.set(f"检测识别完成! 找到 {len(results)} 个车牌")

        except Exception as e:
            self.status_var.set(f"检测识别失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")

    def save_result(self):
        """保存检测结果"""
        if self.detection_results is None:
            self.status_var.set("没有检测结果可保存!")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存结果",
            defaultextension=".jpg",
            filetypes=[("JPEG files", "*.jpg"), ("PNG files", "*.png"), ("All files", "*.*")]
        )

        if file_path:
            try:
                # 重新生成结果图像
                _, original_img = self.detector.detect(
                    self.original_image_path,
                    conf_thres=self.conf_threshold.get()
                )

                result_img = original_img.copy()
                for result in self.detection_results:
                    bbox = result['bbox']
                    class_name = result['class_name']
                    confidence = result['confidence']
                    mask = result['mask']

                    if class_name == 'blue':
                        bbox_color = (255, 0, 0)
                        color_name = "蓝色"
                    elif class_name == 'green':
                        bbox_color = (0, 255, 0)
                        color_name = "绿色"
                    else:
                        bbox_color = (0, 255, 255)
                        color_name = "黄色"

                    # 绘制掩码
                    if mask is not None:
                        try:
                            if hasattr(mask, 'cpu'):
                                mask_np = mask.cpu().numpy()
                            else:
                                mask_np = mask
                            mask_binary = (mask_np > 0.5).astype(np.uint8)
                            overlay = result_img.copy()
                            overlay[mask_binary > 0] = [50, 50, 200]
                            result_img = cv2.addWeighted(overlay, 0.4, result_img, 0.6, 0)
                        except Exception:
                            pass

                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(result_img, (x1, y1), (x2, y2), bbox_color, 2)

                    # 裁剪车牌区域进行识别
                    plate_region = original_img[y1:y2, x1:x2]
                    plate_number = "识别失败"
                    if plate_region.size > 0:
                        # 获取对应的掩码区域
                        mask_region = None
                        if mask is not None:
                            try:
                                if hasattr(mask, 'cpu'):
                                    mask_np = mask.cpu().numpy()
                                else:
                                    mask_np = mask
                                mask_region = mask_np[y1:y2, x1:x2]
                            except Exception as e:
                                print(f"获取掩码区域错误: {e}")

                        plate_number = self.recognizer.recognize_with_mask(plate_region, mask_region)

                    display_text = f"{color_name} {plate_number}"
                    text_pos = (x1, max(y1 - 30, 30))
                    result_img = cv2ImgAddText(result_img, display_text, text_pos, (255, 255, 255), 16)

                cv2.imwrite(file_path, result_img)
                self.status_var.set(f"结果已保存: {file_path}")

            except Exception as e:
                self.status_var.set(f"保存失败: {e}")


def main():
    root = tk.Tk()
    app = LicensePlateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()