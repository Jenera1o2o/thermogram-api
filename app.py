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


def mark_defects(image_bytes, defects, panel_width_mm=500, panel_height_mm=400):
    """
    Наносит красные маркеры на дефекты
    
    ОБНОВЛЁННАЯ ВЕРСИЯ:
    - Принимает координаты в МИЛЛИМЕТРАХ (x_mm, y_mm)
    - Автоматически конвертирует mm → px
    - Поддерживает старый формат (x, y в пикселях) для обратной совместимости
    
    Параметры:
    - image_bytes: изображение в байтах
    - defects: список дефектов с координатами
    - panel_width_mm: ширина панели в мм (по умолчанию 500mm)
    - panel_height_mm: высота панели в мм (по умолчанию 400mm)
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = img.size
    
    # Вычисляем масштаб px/mm
    scale_x = width / panel_width_mm
    scale_y = height / panel_height_mm
    
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font = ImageFont.load_default()
        font_small = font
    
    for i, defect in enumerate(defects, 1):
        defect_id = defect.get('id', i)
        
        # Определяем формат координат (новый в mm или старый в px)
        if 'x_mm' in defect:
            # Новый формат: координаты в миллиметрах
            x_mm = float(defect.get('x_mm', 0))
            y_mm = float(defect.get('y_mm', 0))
            x_px = int(x_mm * scale_x)
            y_px = int(y_mm * scale_y)
        else:
            # Старый формат: координаты уже в пикселях
            x_px = int(defect.get('x', 0))
            y_px = int(defect.get('y', 0))
        
        # Размер дефекта
        diameter_mm = float(defect.get('diameter_mm', defect.get('size', 10)))
        radius_px = int((diameter_mm / 2) * scale_x)
        
        if radius_px < 15:
            radius_px = 15
        if radius_px > 100:
            radius_px = 100
        
        # Цвет в зависимости от severity
        severity = defect.get('severity', 'medium').lower()
        if severity == 'high':
            color = (255, 0, 0, 255)       # Красный
            color_rgb = (255, 0, 0)
        elif severity == 'medium':
            color = (255, 140, 0, 255)     # Оранжевый
            color_rgb = (255, 140, 0)
        else:  # low
            color = (255, 200, 0, 255)     # Жёлтый
            color_rgb = (255, 200, 0)
        
        # ===== РИСУЕМ МАРКЕР =====
        
        # Внешний круг (основной)
        draw.ellipse(
            [(x_px - radius_px, y_px - radius_px), 
             (x_px + radius_px, y_px + radius_px)],
            outline=color,
            width=4
        )
        
        # Второй круг (для видимости)
        draw.ellipse(
            [(x_px - radius_px - 2, y_px - radius_px - 2), 
             (x_px + radius_px + 2, y_px + radius_px + 2)],
            outline=(255, 255, 255, 180),
            width=1
        )
        
        # Центральная точка
        dot_radius = 5
        draw.ellipse(
            [(x_px - dot_radius, y_px - dot_radius), 
             (x_px + dot_radius, y_px + dot_radius)],
            fill=color
        )
        
        # Перекрестие в центре
        cross_size = 8
        draw.line([(x_px - cross_size, y_px), (x_px + cross_size, y_px)], 
                  fill=color, width=2)
        draw.line([(x_px, y_px - cross_size), (x_px, y_px + cross_size)], 
                  fill=color, width=2)
        
        # ===== ПОДПИСИ =====
        
        # Номер дефекта (сверху слева от круга)
        label_num = f"#{defect_id}"
        num_x = x_px - radius_px - 5
        num_y = y_px - radius_px - 30
        
        # Фон для номера
        try:
            bbox = draw.textbbox((num_x, num_y), label_num, font=font)
            padding = 3
            draw.rectangle(
                [bbox[0] - padding, bbox[1] - padding, 
                 bbox[2] + padding, bbox[3] + padding],
                fill=(0, 0, 0, 220)
            )
        except:
            draw.rectangle(
                [num_x - 3, num_y - 3, num_x + 40, num_y + 25],
                fill=(0, 0, 0, 220)
            )
        draw.text((num_x, num_y), label_num, fill=color, font=font)
        
        # Размер в мм (снизу от круга)
        size_label = f"{diameter_mm:.1f} mm"
        size_x = x_px - radius_px
        size_y = y_px + radius_px + 8
        
        # Фон для размера
        try:
            bbox = draw.textbbox((size_x, size_y), size_label, font=font_small)
            padding = 3
            draw.rectangle(
                [bbox[0] - padding, bbox[1] - padding, 
                 bbox[2] + padding, bbox[3] + padding],
                fill=(0, 0, 0, 220)
            )
        except:
            draw.rectangle(
                [size_x - 3, size_y - 3, size_x + 70, size_y + 20],
                fill=(0, 0, 0, 220)
            )
        draw.text((size_x, size_y), size_label, fill=(255, 255, 255, 255), font=font_small)
        
        # Координаты в мм (опционально, справа от круга)
        if 'x_mm' in defect:
            coord_label = f"[{defect.get('x_mm', 0):.0f}, {defect.get('y_mm', 0):.0f}]"
            coord_x = x_px + radius_px + 8
            coord_y = y_px - 10
            
            try:
                bbox = draw.textbbox((coord_x, coord_y), coord_label, font=font_small)
                padding = 2
                draw.rectangle(
                    [bbox[0] - padding, bbox[1] - padding, 
                     bbox[2] + padding, bbox[3] + padding],
                    fill=(0, 0, 0, 200)
                )
            except:
                pass
            draw.text((coord_x, coord_y), coord_label, fill=(200, 200, 200, 255), font=font_small)
    
    # ===== ЛЕГЕНДА =====
    if defects:
        legend_x = width - 200
        legend_y = 20
        
        # Фон легенды
        draw.rectangle(
            [legend_x - 10, legend_y - 10, width - 10, legend_y + 90],
            fill=(0, 0, 0, 200)
        )
        
        draw.text((legend_x, legend_y), "Дефекты:", fill=(255, 255, 255, 255), font=font)
        draw.ellipse([legend_x, legend_y + 30, legend_x + 12, legend_y + 42], fill=(255, 0, 0, 255))
        draw.text((legend_x + 18, legend_y + 28), "high", fill=(255, 255, 255, 255), font=font_small)
        
        draw.ellipse([legend_x + 70, legend_y + 30, legend_x + 82, legend_y + 42], fill=(255, 140, 0, 255))
        draw.text((legend_x + 88, legend_y + 28), "med", fill=(255, 255, 255, 255), font=font_small)
        
        draw.ellipse([legend_x, legend_y + 55, legend_x + 12, legend_y + 67], fill=(255, 200, 0, 255))
        draw.text((legend_x + 18, legend_y + 53), "low", fill=(255, 255, 255, 255), font=font_small)
        
        # Общее количество
        total_text = f"Всего: {len(defects)}"
        draw.text((legend_x + 70, legend_y + 53), total_text, fill=(255, 255, 255, 255), font=font_small)
    
    # Объединяем слои
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
        "description": "Анализ термограмм склейки панелей",
        "panel_size": "500×400mm (настраиваемо)",
        "grid": "Small: 24px, Large: 118px",
        "endpoints": {
            "/overlay-grid": {
                "method": "POST",
                "description": "Накладывает измерительную сетку на изображение",
                "params": "image (file/base64), grid_step_small, grid_step_large, opacity"
            },
            "/mark-defects": {
                "method": "POST", 
                "description": "Наносит маркеры на дефекты",
                "params": "image (file/base64), defects (JSON array), panel_width_mm, panel_height_mm",
                "defect_format": {
                    "new": {"x_mm": "float", "y_mm": "float", "diameter_mm": "float", "severity": "high/medium/low"},
                    "legacy": {"x": "int (px)", "y": "int (px)", "size": "float (mm)"}
                }
            },
            "/health": {
                "method": "GET",
                "description": "Проверка работоспособности"
            }
        },
        "changelog": {
            "v2.0": "Добавлена поддержка координат в мм (x_mm, y_mm), цветовая кодировка severity, легенда"
        }
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0"
    })


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
        grid_step_small = 24
        grid_step_large = 118
        opacity = 160
        
        if request.form:
            grid_step_small = int(request.form.get('grid_step_small', 24))
            grid_step_large = int(request.form.get('grid_step_large', 118))
            opacity = int(request.form.get('opacity', 160))
        elif request.is_json and request.json:
            grid_step_small = int(request.json.get('grid_step_small', 24))
            grid_step_large = int(request.json.get('grid_step_large', 118))
            opacity = int(request.json.get('opacity', 160))
        
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
    
    Поддерживает два формата дефектов:
    1. Новый (рекомендуемый): x_mm, y_mm, diameter_mm в миллиметрах
    2. Старый (legacy): x, y в пикселях, size в мм
    
    Параметры:
    - image: файл или base64
    - defects: JSON массив дефектов
    - panel_width_mm: ширина панели в мм (по умолчанию 500)
    - panel_height_mm: высота панели в мм (по умолчанию 400)
    """
    try:
        image_bytes = None
        defects = []
        panel_width_mm = 500
        panel_height_mm = 400
        
        # Получаем изображение
        if request.files and 'image' in request.files:
            image_bytes = request.files['image'].read()
        elif request.is_json and request.json and 'image_base64' in request.json:
            image_base64 = request.json['image_base64']
            image_bytes = base64.b64decode(image_base64)
        elif request.data and len(request.data) > 0 and not request.is_json:
            image_bytes = request.data
        
        if not image_bytes:
            return jsonify({"error": "No image provided. Send as 'image' file or 'image_base64' in JSON"}), 400
        
        # Получаем дефекты и параметры панели
        if request.is_json and request.json:
            defects = request.json.get('defects', [])
            panel_width_mm = float(request.json.get('panel_width_mm', 500))
            panel_height_mm = float(request.json.get('panel_height_mm', 400))
        elif request.form:
            defects_str = request.form.get('defects', '[]')
            defects = json.loads(defects_str)
            panel_width_mm = float(request.form.get('panel_width_mm', 500))
            panel_height_mm = float(request.form.get('panel_height_mm', 400))
        
        if not defects:
            return jsonify({"error": "No defects provided. Send as 'defects' JSON array"}), 400
        
        # Обрабатываем
        result_bytes = mark_defects(image_bytes, defects, panel_width_mm, panel_height_mm)
        
        # Возвращаем
        return send_file(
            io.BytesIO(result_bytes),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name='marked_defects.jpg'
        )
            
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid JSON in defects: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e), "type": str(type(e).__name__)}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Thermogram API v2.0 on port {port}")
    app.run(host='0.0.0.0', port=port)
