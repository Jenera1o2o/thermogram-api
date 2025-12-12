from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import json
from datetime import datetime
import cv2
import numpy as np

app = Flask(__name__)

def overlay_grid(image_bytes, grid_step_small=24, grid_step_large=118, opacity=160):
    """
    Накладывает двухуровневую сетку на изображение
    
    Параметры:
    - grid_step_small: шаг мелкой сетки в пикселях (24px)
    - grid_step_large: шаг крупной сетки в пикселях (118px)
    - opacity: прозрачность линий (0-255)
    
    Реальный размер панели: 290×218mm
    """
    # Открываем изображение
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = img.size
    
    # Создаем слой для сетки
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Цвета линий
    color_small = (120, 120, 120, opacity // 2)
    color_large = (80, 80, 80, opacity)
    
    # Рисуем мелкую сетку (вертикальные)
    for x in range(0, width, grid_step_small):
        draw.line([(x, 0), (x, height)], fill=color_small, width=1)
    
    # Рисуем мелкую сетку (горизонтальные)
    for y in range(0, height, grid_step_small):
        draw.line([(0, y), (width, y)], fill=color_small, width=1)
    
    # Рисуем крупную сетку (вертикальные)
    for x in range(0, width, grid_step_large):
        draw.line([(x, 0), (x, height)], fill=color_large, width=3)
    
    # Рисуем крупную сетку (горизонтальные)
    for y in range(0, height, grid_step_large):
        draw.line([(0, y), (width, y)], fill=color_large, width=3)
    
    # Шрифт для подписей
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # Расчет реального шага в мм для панели 290×218mm
    num_cells_x = width // grid_step_large
    num_cells_y = height // grid_step_large
    
    step_mm_x = 290 / num_cells_x if num_cells_x > 0 else 50
    step_mm_y = 218 / num_cells_y if num_cells_y > 0 else 50
    
    # Подписи по оси X (верх)
    for i, x in enumerate(range(0, width, grid_step_large)):
        label = f"{int(i * step_mm_x)}mm"
        try:
            bbox = draw.textbbox((x + 5, 5), label, font=font)
            draw.rectangle(bbox, fill=(0, 0, 0, 180))
        except:
            pass
        draw.text((x + 5, 5), label, fill=(255, 255, 255, 255), font=font)
    
    # Подписи по оси Y (слева)
    for i, y in enumerate(range(0, height, grid_step_large)):
        label = f"{int(i * step_mm_y)}mm"
        try:
            bbox = draw.textbbox((5, y + 5), label, font=font)
            draw.rectangle(bbox, fill=(0, 0, 0, 180))
        except:
            pass
        draw.text((5, y + 5), label, fill=(255, 255, 255, 255), font=font)
    
    # Объединяем слои
    img = Image.alpha_composite(img, overlay)
    img = img.convert('RGB')
    
    # Сохраняем
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=95)
    output.seek(0)
    
    return output.getvalue()


def mark_defects(image_bytes, defects):
    """
    Наносит красные маркеры на дефекты
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    for i, defect in enumerate(defects, 1):
        x = int(defect.get('x', 0))
        y = int(defect.get('y', 0))
        size = float(defect.get('size', 10))
        temp = defect.get('temp', 0)
        
        # Радиус маркера (масштаб 2.36 px/mm)
        radius = int(size * 2.36 / 2)
        if radius < 15:
            radius = 15
        
        # Красный круг
        draw.ellipse(
            [(x - radius, y - radius), (x + radius, y + radius)],
            outline=(255, 0, 0, 255),
            width=4
        )
        
        # Центральная точка
        draw.ellipse(
            [(x - 5, y - 5), (x + 5, y + 5)],
            fill=(255, 0, 0, 255)
        )
        
        # Номер дефекта
        label_num = f"#{i}"
        try:
            bbox = draw.textbbox((x - radius - 10, y - radius - 35), label_num, font=font)
            draw.rectangle(bbox, fill=(0, 0, 0, 200))
        except:
            pass
        draw.text((x - radius - 10, y - radius - 35), label_num, 
                 fill=(255, 0, 0, 255), font=font)
        
        # Информация о дефекте
        info = f"{size}mm"
        if temp:
            info += f" | {temp}°C"
        try:
            bbox = draw.textbbox((x - radius - 10, y + radius + 10), info, font=font_small)
            draw.rectangle(bbox, fill=(0, 0, 0, 200))
        except:
            pass
        draw.text((x - radius - 10, y + radius + 10), info, 
                 fill=(255, 255, 255, 255), font=font_small)
    
    # Объединяем
    img = Image.alpha_composite(img, overlay)
    img = img.convert('RGB')
    
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=95)
    output.seek(0)
    
    return output.getvalue()


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "service": "Thermogram Processing API",
        "version": "2.0",
        "panel_size": "290×218mm",
        "detection_methods": ["opencv", "manual"],
        "endpoints": {
            "/overlay-grid": "POST - Накладывает сетку на изображение",
            "/detect-defects-opencv": "POST - Детекция дефектов через OpenCV",
            "/mark-defects": "POST - Наносит маркеры на дефекты",
            "/health": "GET - Проверка работоспособности"
        }
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route('/overlay-grid', methods=['POST'])
def api_overlay_grid():
    """
    Принимает изображение, возвращает с сеткой
    """
    try:
        image_bytes = None
        
        # Получаем изображение
        if request.files and 'image' in request.files:
            image_bytes = request.files['image'].read()
        elif request.is_json and request.json and 'image_base64' in request.json:
            image_base64 = request.json['image_base64']
            image_bytes = base64.b64decode(image_base64)
        elif request.data and len(request.data) > 0:
            image_bytes = request.data
        
        if not image_bytes:
            return jsonify({"error": "No image provided"}), 400
        
        # Параметры сетки
        grid_step_small = int(request.form.get('grid_step_small', 24)) if request.form else 24
        grid_step_large = int(request.form.get('grid_step_large', 118)) if request.form else 118
        opacity = int(request.form.get('opacity', 160)) if request.form else 160
        
        # Обрабатываем
        result_bytes = overlay_grid(image_bytes, grid_step_small, grid_step_large, opacity)
        
        # Возвращаем
        return send_file(
            io.BytesIO(result_bytes),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name='grid_overlay.jpg'
        )
            
    except Exception as e:
        return jsonify({"error": str(e), "type": str(type(e).__name__)}), 500


@app.route('/detect-defects-opencv', methods=['POST'])
def api_detect_defects_opencv():
    """
    Детекция дефектов через компьютерное зрение OpenCV
    """
    try:
        # Получаем изображение
        if request.files and 'image' in request.files:
            image_bytes = request.files['image'].read()
        else:
            return jsonify({"error": "No image provided"}), 400
        
        # Параметры (можно настроить)
        threshold_value = int(request.form.get('threshold', 90)) if request.form else 90
        min_area = int(request.form.get('min_area', 150)) if request.form else 150
        
        # Конвертируем в numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Invalid image format"}), 400
        
        # Конвертируем в grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Применяем размытие для уменьшения шума
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Пороговая обработка для поиска ТЕМНЫХ областей (дефектов)
        _, thresh = cv2.threshold(blurred, threshold_value, 255, cv2.THRESH_BINARY_INV)
        
        # Морфологические операции для улучшения детекции
        kernel = np.ones((7, 7), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Находим контуры
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        defects = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Фильтруем слишком маленькие области (шум)
            if area < min_area:
                continue
            
            # Получаем центр масс
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
                
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Вычисляем размер
            (x, y, w, h) = cv2.boundingRect(contour)
            diameter_px = max(w, h)
            diameter_mm = round(diameter_px / 2.36, 1)  # Масштаб 2.36 px/mm
            
            # Оценка серьезности
            if diameter_mm > 20:
                severity = "high"
            elif diameter_mm > 10:
                severity = "medium"
            else:
                severity = "low"
            
            # Вычисляем среднюю яркость области
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            mean_val = cv2.mean(gray, mask=mask)[0]
            
            defects.append({
                "x": cx,
                "y": cy,
                "size": diameter_mm,
                "temp": 0,
                "severity": severity,
                "description": f"Дефект {diameter_mm}мм (яркость: {int(mean_val)})",
                "area_px": int(area),
                "brightness": int(mean_val)
            })
        
        # Сортируем по размеру (от большего к меньшему)
        defects.sort(key=lambda d: d['size'], reverse=True)
        
        return jsonify({
            "defects": defects,
            "image_width": img.shape[1],
            "image_height": img.shape[0],
            "total_defects": len(defects),
            "method": "opencv",
            "summary": f"Обнаружено {len(defects)} дефектов методом компьютерного зрения",
            "quality_assessment": "плохо" if len(defects) > 5 else ("удовлетворительно" if len(defects) > 2 else "хорошо"),
            "parameters": {
                "threshold": threshold_value,
                "min_area": min_area
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "type": str(type(e).__name__)}), 500


@app.route('/mark-defects', methods=['POST'])
def api_mark_defects():
    """
    Принимает изображение и дефекты, возвращает с маркерами
    """
    try:
        image_bytes = None
        
        # Получаем изображение
        if request.files and 'image' in request.files:
            image_bytes = request.files['image'].read()
        elif request.is_json and request.json and 'image_base64' in request.json:
            image_base64 = request.json['image_base64']
            image_bytes = base64.b64decode(image_base64)
        elif request.data and len(request.data) > 0:
            image_bytes = request.data
        
        if not image_bytes:
            return jsonify({"error": "No image provided"}), 400
        
        # Получаем дефекты
        if request.is_json and request.json:
            defects = request.json.get('defects', [])
        elif request.form:
            defects_str = request.form.get('defects', '[]')
            defects = json.loads(defects_str)
        else:
            defects = []
        
        if not defects:
            return jsonify({"error": "No defects provided"}), 400
        
        # Обрабатываем
        result_bytes = mark_defects(image_bytes, defects)
        
        # Возвращаем
        return send_file(
            io.BytesIO(result_bytes),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name='marked_defects.jpg'
        )
            
    except Exception as e:
        return jsonify({"error": str(e), "type": str(type(e).__name__)}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
