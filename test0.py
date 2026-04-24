import os
import cv2

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR

img_path = r'F:\2ziyuan\python111\ZMD\test_commission.png'

img = cv2.imread(img_path)
if img is None:
    raise FileNotFoundError(img_path)

# 放大
img = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

# 灰度
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 二值化
_, binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)

# 转回三通道
binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

# 保存看看
debug_path = r'F:\2ziyuan\python111\ZMD\test_commission_preprocessed.png'
cv2.imwrite(debug_path, binary)

ocr = PaddleOCR(
    use_textline_orientation=False,
    lang='ch'
)

result = ocr.predict(binary_bgr)
print(result)