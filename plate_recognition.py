# plate_recognition.py
import os
import sys
import cv2
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import yaml

# 添加YOLOv5路径
current_dir = os.path.dirname(os.path.abspath(__file__))
yolov5_path = os.path.join(current_dir, 'yolov5')
if os.path.exists(yolov5_path):
    sys.path.insert(0, yolov5_path)

# 导入YOLOv5模块
from YOLOv5.models.common import DetectMultiBackend
from YOLOv5.utils.general import check_img_size, non_max_suppression, scale_boxes
from YOLOv5.utils.segment.general import process_mask_native

# 导入LPRNet
from YOLOv5.models.LPRNet import LPRNet, CHARS


# ==================== 工具函数 ====================
def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    """调整图像尺寸并填充"""
    shape = im.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:
        r = min(r, 1.0)

    ratio = r, r
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    if auto:
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
    elif scaleFill:
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]

    dw /= 2
    dh /= 2

    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, ratio, (dw, dh)


def cv2ImgAddText(img, text, pos, textColor=(255, 255, 255), textSize=16):
    """在OpenCV图像上添加中文文本"""
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    # 尝试加载中文字体
    font_path = os.path.join(current_dir, 'static', 'fonts', 'simhei.ttf')
    try:
        font = ImageFont.truetype(font_path, textSize, encoding="utf-8")
    except:
        font = ImageFont.load_default()
    draw.text(pos, text, textColor, font=font)
    return cv2.cvtColor(np.asarray(img_pil), cv2.COLOR_RGB2BGR)


# ==================== 检测器 ====================
class LicensePlateDetector:
    def __init__(self, weights_path, hyp_path, data_path, device='cpu'):
        self.device = torch.device(device)
        self.model = DetectMultiBackend(weights_path, device=self.device, dnn=False, data=data_path, fp16=False)
        self.stride = self.model.stride
        self.names = self.model.names
        self.pt = self.model.pt
        self.imgsz = check_img_size((640, 640), s=self.stride)

        with open(hyp_path, 'r', encoding='utf-8') as f:
            self.hyp = yaml.safe_load(f)
        with open(data_path, 'r', encoding='utf-8') as f:
            self.data_cfg = yaml.safe_load(f)

        self.model.eval()

    def detect(self, image_path, conf_thres=0.25, iou_thres=0.45):
        """执行检测，返回结果列表和原始图像"""
        img0 = cv2.imread(image_path)
        if img0 is None:
            raise ValueError(f"无法读取图像: {image_path}")

        original_img = img0.copy()

        # 预处理
        img, ratio, dwdh = letterbox(img0, self.imgsz, stride=self.stride, auto=self.pt)
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR->RGB, HWC->CHW
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device)
        img = img.float() / 255.0
        if len(img.shape) == 3:
            img = img[None]

        # 推理
        with torch.no_grad():
            pred, proto = self.model(img, augment=False, visualize=False)[:2]

        # NMS
        pred = non_max_suppression(pred, conf_thres, iou_thres, classes=None, agnostic=False, max_det=1000, nm=32)

        results = []
        for i, det in enumerate(pred):
            if len(det):
                det[:, :4] = scale_boxes(img.shape[2:], det[:, :4], img0.shape).round()
                masks = []
                if proto is not None:
                    masks = process_mask_native(proto[i], det[:, 6:], det[:, :4], img0.shape[:2])

                for j, (*xyxy, conf, cls) in enumerate(reversed(det[:, :6])):
                    class_name = self.names[int(cls)]
                    confidence = float(conf)
                    mask = masks[j] if len(masks) > j else None
                    results.append({
                        'bbox': [int(x) for x in xyxy],
                        'class_name': class_name,
                        'confidence': confidence,
                        'mask': mask
                    })

        return results, original_img


# ==================== 识别器 ====================
class LPRNetRecognizer:
    def __init__(self, weights_path, device='cpu'):
        self.device = torch.device(device)
        self.lpr_max_len = 8
        self.class_num = len(CHARS)

        self.model = LPRNet(lpr_max_len=self.lpr_max_len, phase=False, class_num=self.class_num, dropout_rate=0)
        self.model.load_state_dict(torch.load(weights_path, map_location=device))
        self.model.to(device)
        self.model.eval()

    def preprocess_plate(self, plate_image):
        """预处理车牌图像"""
        plate_resized = cv2.resize(plate_image, (94, 24))
        plate_rgb = cv2.cvtColor(plate_resized, cv2.COLOR_BGR2RGB)
        plate_normalized = plate_rgb.astype('float32')
        plate_normalized -= 127.5
        plate_normalized *= 0.0078125
        plate_tensor = np.transpose(plate_normalized, (2, 0, 1))
        plate_tensor = torch.from_numpy(plate_tensor).unsqueeze(0).to(self.device)
        return plate_tensor

    def greedy_decode(self, preds):
        """贪心解码"""
        pred_labels = []
        preds = preds.cpu().detach().numpy()
        for i in range(preds.shape[0]):
            pred = preds[i, :, :]
            pred_label = []
            for j in range(pred.shape[1]):
                pred_label.append(np.argmax(pred[:, j], axis=0))
            no_repeat_blank_label = []
            pre_c = pred_label[0]
            if pre_c != len(CHARS) - 1:
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
        """识别车牌号码"""
        try:
            plate_tensor = self.preprocess_plate(plate_image)
            with torch.no_grad():
                preds = self.model(plate_tensor)
            pred_labels = self.greedy_decode(preds)
            if pred_labels:
                plate_text = ''.join([CHARS[i] for i in pred_labels[0]])
                return plate_text
            return "识别失败"
        except Exception as e:
            print(f"识别错误: {e}")
            return "识别错误"


# ==================== 识别主函数 ====================
class PlateRecognizer:
    def __init__(self, detector_weights, detector_hyp, detector_data, recognizer_weights, device='cpu'):
        self.detector = LicensePlateDetector(detector_weights, detector_hyp, detector_data, device)
        self.recognizer = LPRNetRecognizer(recognizer_weights, device)

    def recognize(self, image_path, conf_thres=0.25):
        """识别图像中的车牌，返回标注图像和结果列表"""
        results, original_img = self.detector.detect(image_path, conf_thres=conf_thres)
        annotated_img = original_img.copy()
        plates_info = []

        for res in results:
            bbox = res['bbox']
            class_name = res['class_name']
            confidence = res['confidence']
            mask = res['mask']

            # 确定颜色名称和边界框颜色
            if class_name == 'blue':
                color_name = "蓝色"
                bbox_color = (255, 0, 0)  # BGR
            elif class_name == 'green':
                color_name = "绿色"
                bbox_color = (0, 255, 0)
            else:  # yellow
                color_name = "黄色"
                bbox_color = (0, 255, 255)

            # 绘制掩码（如果有）
            if mask is not None:
                try:
                    mask_np = mask.cpu().numpy() if hasattr(mask, 'cpu') else mask
                    mask_binary = (mask_np > 0.5).astype(np.uint8)
                    overlay = annotated_img.copy()
                    overlay[mask_binary > 0] = [50, 50, 200]  # 淡红色
                    annotated_img = cv2.addWeighted(overlay, 0.4, annotated_img, 0.6, 0)
                except Exception as e:
                    print(f"掩码绘制错误: {e}")

            # 裁剪车牌区域
            x1, y1, x2, y2 = bbox
            plate_region = original_img[y1:y2, x1:x2].copy()
            plate_number = "识别失败"
            if plate_region.size > 0:
                plate_number = self.recognizer.recognize(plate_region)

            # 保存识别结果
            plates_info.append({
                'color': color_name,
                'number': plate_number,
                'confidence': round(confidence, 2),
                'bbox': bbox
            })

            # 绘制边界框和文字
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), bbox_color, 2)
            #display_text = f"{color_name} {plate_number}"
            #text_pos = (x1, max(y1 - 30, 30))
            #annotated_img = cv2ImgAddText(annotated_img, display_text, text_pos, (255, 255, 255), 16)

            # 绘制置信度
            #cv2.rectangle(annotated_img, (x1, text_pos[1] + 20), (x1 + 120, text_pos[1] + 35), bbox_color, -1)
            #annotated_img = cv2ImgAddText(annotated_img, f"置信度: {confidence:.2f}", (x1, text_pos[1] + 20), (255, 255, 255), 12)
            #取消上面的5条注释，识别结果图片会显示识别信息
        return annotated_img, plates_info
