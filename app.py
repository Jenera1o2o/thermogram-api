from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import json
from datetime import datetime

app = Flask(__name__)

def overlay_grid(image_bytes, grid_step_small=5, grid_step_large=50, opacity=128):
    """
    Накладывает двухуровневую сетку на изображение
    
    Параметры:
    - grid_step_small: шаг мелкой сетки в пикселях (по умолчанию 5px = 0.5см)
    - grid_step_large: шаг крупной сетки в пикселях (по умолчанию 50px = 5см)
    - opacity: прозрачность линий (0-255, по умолчанию 128)
    """
    # Открываем изображение
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = img.size
    
    # Создаем слой для сетки
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Цвета линий (серый с прозрачностью)
    color_small = (128, 128, 128, opacity // 2)  # Более прозрачная мелкая сетка
    color_large = (100, 100, 100, opacity)  # Менее прозрачная крупная сетка
    
    # Рисуем мелкую сетку (вертикальные линии)
    for x in range(0, width, grid_step_small):
        draw.line([(x, 0), (x, height)], fill=color_small, width=1)
    
    # Рисуем мелкую сетку (горизонтальные линии)
    for y in range(0, height, grid_step_small):
        draw.line([(0, y), (width, y)], fill=color_small, width=1)
    
    # Рисуем крупную сетку (вертикальные линии)
    for x in range(0, width, grid_step_large):
        draw.line([(x, 0), (x, height)], fill=color_large, width=2)
    
    # Рисуем крупную сетку (горизонтальные линии)
    for y in range(0, height, grid_step_large):
        draw.line([(0, y), (width, y)], fill=color_large, width=2)
    
    # Добавляем подписи координат
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()
    
   # Подписи по оси X (верх) - каждые 50мм
for i, x in enumerate(range(0, width, grid_step_large)):
    label = f"{i * 50}mm"  # 0, 50, 100, 150...
    draw.text((x + 5, 5), label, fill=(255, 255, 255, 255), font=font)

# Подписи по оси Y (слева) - каждые 50мм
for i, y in enumerate(range(0, height, grid_step_large)):
    label = f"{i * 50}mm"
    draw.text((5, y + 5), label, fill=(255, 255, 255, 255), font=font)
    
    # Объединяем слои
    img = Image.alpha_composite(img, overlay)
    
    # Конвертируем обратно в RGB для сохранения как JPEG
    img = img.convert('RGB')
    
    # Сохраняем в байты
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=95)
    output.seek(0)
    
    return output.getvalue()


def mark_defects(image_bytes, defects):
    """
    Наносит красные маркеры на дефекты
    
    defects: список словарей с координатами
    [
        {"x": 150, "y": 200, "size": 14.8, "temp": 183.4},
        {"x": 400, "y": 220, "size": 14.0, "temp": 145.3}
    ]
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    for i, defect in enumerate(defects, 1):
        x = defect.get('x', 0)
        y = defect.get('y', 0)
        size = defect.get('size', 10)
        temp = defect.get('temp', 0)
        
        # Радиус маркера (пропорционально размеру дефекта)
        radius = int(size * 2)
        
        # Рисуем красный круг
        draw.ellipse(
            [(x - radius, y - radius), (x + radius, y + radius)],
            outline=(255, 0, 0, 255),
            width=3
        )
        
        # Центральная точка
        draw.ellipse(
            [(x - 3, y - 3), (x + 3, y + 3)],
            fill=(255, 0, 0, 255)
        )
        
        # Номер дефекта
        label_num = f"#{i}"
        draw.text((x - radius - 5, y - radius - 25), label_num, 
                 fill=(255, 0, 0, 255), font=font)
        
        # Информация о дефекте
        info = f"{size}mm | {temp}°C"
        draw.text((x - radius - 5, y + radius + 5), info, 
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
        "version": "1.0",
        "endpoints": {
            "/overlay-grid": "POST - Накладывает сетку на изображение",
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
    Принимает изображение как файл или base64
    Возвращает изображение с сеткой
    """
    try:
        image_bytes = None
        
        # Вариант 1: Файл в form-data
        if request.files and 'image' in request.files:
            image_bytes = request.files['image'].read()
        
        # Вариант 2: Base64 в JSON
        elif request.is_json and request.json and 'image_base64' in request.json:
            image_base64 = request.json['image_base64']
            image_bytes = base64.b64decode(image_base64)
        
        # Вариант 3: Raw binary в body
        elif request.data and len(request.data) > 0:
            image_bytes = request.data
        
        if not image_bytes:
            return jsonify({"error": "No image provided. Send as 'image' file in form-data or 'image_base64' in JSON"}), 400
        
       # Параметры сетки (для панели 290×218мм = 2064×1544px)
        # Масштаб: ~7.1 px/mm
        grid_step_small = int(request.form.get('grid_step_small', 36)) if request.form else 36  # 5мм
        grid_step_large = int(request.form.get('grid_step_large', 355)) if request.form else 355  # 50мм
        opacity = int(request.form.get('opacity', 128)) if request.form else 128
        
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
        return jsonify({"error": str(e)}), 500


@app.route('/mark-defects', methods=['POST'])
def api_mark_defects():
    """
    Принимает изображение и список дефектов
    Возвращает изображение с маркерами
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
        
        # Получаем список дефектов
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
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
