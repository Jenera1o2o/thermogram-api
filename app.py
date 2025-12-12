from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import json
from datetime import datetime

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
        "version": "1.3",
        "panel_size": "290×218mm",
        "grid": "Small: 24px, Large: 118px",
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
