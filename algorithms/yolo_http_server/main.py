from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from ultralytics import YOLO
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os

app = FastAPI()

# 加载 YOLO 模型
model = YOLO(os.path.dirname(__file__) + "/yolo26n.pt")


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        # 读取上传文件到PIL Image
        image = Image.open(BytesIO(await file.read())).convert("RGB")
        # 转为 numpy 数组
        img_array = np.array(image)

        # 模型预测
        results = model.predict(img_array, imgsz=640)  # 可以设置更高精度

        # 解析结果
        predictions = []
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
            scores = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()

            for box, score, cls in zip(boxes, scores, class_ids):
                predictions.append(
                    {
                        "box": box.tolist(),
                        "score": float(score),
                        "class_id": int(cls),
                        "class_name": result.names[int(cls)],
                    }
                )

        return JSONResponse({"predictions": predictions})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/predict/vis")
async def predict_vis(file: UploadFile = File(...)):
    try:
        image = Image.open(BytesIO(await file.read())).convert("RGB")
        img_array = np.array(image)
        results = model.predict(img_array, imgsz=640)

        # 绘制框
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()

            for box, score, cls in zip(boxes, scores, class_ids):
                x1, y1, x2, y2 = box
                class_name = result.names[int(cls)]
                draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
                draw.text(
                    (x1, y1 - 10), f"{class_name} {score:.2f}", fill="red", font=font
                )

        # 转为字节流返回
        buf = BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
