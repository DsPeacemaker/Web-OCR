import pytesseract
import cv2 as cv
import os
import aspose.words as aw
import uuid
from fpdf import FPDF
import numpy as np
import utils
import xlsxwriter
from table import Table
from flask import Flask, render_template, request, redirect, flash, send_from_directory
#from werkzeug.utils import secure_filename
pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

UPLOAD_FOLDER = 'C:/Users/denis/PycharmProjects/Web/uploads'
RESULT_FOLDER = 'C:/Users/denis/PycharmProjects/Web/result'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
MAX_THRESHOLD_VALUE = 255
BLOCK_SIZE = 15
THRESHOLD_CONSTANT = 0
form = ""
language = ""
fname = ""


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global language, form, fname
    if request.method == 'POST':
        form = request.form.get('format')
        language = request.form.get('language')
        if 'file' not in request.files:
            flash('Файл не читается')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('нет выбранного файла')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            #filename = secure_filename(file.filename)
            filename, file_extension = os.path.splitext(file.filename)
            fname = str(uuid.uuid4())
            filename = fname + file_extension
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect('/process/'+filename)
    return render_template('index.html')


@app.route('/process/<filename>', methods=['GET'])
def processing(filename):
    global form, fname
    if request.method == 'GET':
        if form == ".xlsx":
            image = cv.imread('uploads/'+filename)
            grayscale = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
            filtered = cv.adaptiveThreshold(~grayscale, MAX_THRESHOLD_VALUE, cv.ADAPTIVE_THRESH_MEAN_C,
                                            cv.THRESH_BINARY, BLOCK_SIZE, THRESHOLD_CONSTANT)
            """
ГОРИЗОНТАЛЬНАЯ И ВЕРТИКАЛЬНАЯ ИЗОЛЯЦИЯ ЛИНИИ
             Чтобы изолировать вертикальные и горизонтальные линии,

             1. Установите масштаб.
             2. Создайте элемент структурирования.
             3. Изолируйте линии, размывая, а затем расширяя изображение.
            """
            SCALE = 15
            # Изолируйте горизонтальные и вертикальные линии, используя морфологические операции
            horizontal = filtered.copy()
            vertical = filtered.copy()

            horizontal_size = int(horizontal.shape[1] / SCALE)
            horizontal_structure = cv.getStructuringElement(cv.MORPH_RECT, (horizontal_size, 1))
            utils.isolate_lines(horizontal, horizontal_structure)

            vertical_size = int(vertical.shape[0] / SCALE)
            vertical_structure = cv.getStructuringElement(cv.MORPH_RECT, (1, vertical_size))
            utils.isolate_lines(vertical, vertical_structure)

            # Извлечение таблицы
            # Создаем маску изображения только с горизонтальной
            # и вертикальные линии на изображении. Затем найдите
            # все контуры в маске
            mask = horizontal + vertical
            (contours, _) = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

            # Находим пересечения между линиями
            # чтобы определить, являются ли пересечения соединениями таблиц.
            intersections = cv.bitwise_and(horizontal, vertical)

            # Получение таблицы из изображений
            tables = []  # list of tables
            for i in range(len(contours)):
                # Убедитесь, что область интереса является таблицей
                (rect, table_joints) = utils.verify_table(contours[i], intersections)
                if rect == None or table_joints == None:
                    continue

                # Создать новый экземпляр таблицы
                table = Table(rect[0], rect[1], rect[2], rect[3])

                # Получить n-мерный массив координат соединений таблицы
                joint_coords = []
                for i in range(len(table_joints)):
                    joint_coords.append(table_joints[i][0][0])
                joint_coords = np.asarray(joint_coords)

                # Возвращает индексы координат в отсортированном порядке
                # Сортировка по параметрам (также называемым ключами), начиная с последнего параметра, затем предпоследнего и тд
                sorted_indices = np.lexsort((joint_coords[:, 0], joint_coords[:, 1]))
                joint_coords = joint_coords[sorted_indices]

                # Сохранить координаты соединения в экземпляре таблицы
                table.set_joints(joint_coords)
                tables.append(table)

            # Распознавание и импорт в эксель
            out = "bin/"
            table_name = "table.jpg"
            psm = 6
            oem = 3
            mult = 3

            utils.mkdir(out)
            utils.mkdir("bin/table/")
            utils.mkdir("result/")
            name = fname + '.xlsx'
            workbook = xlsxwriter.Workbook('result/'+name)

            for table in tables:
                worksheet = workbook.add_worksheet()
                table_entries = table.get_table_entries
                table_roi = image[table.y:table.y + table.h, table.x:table.x + table.w]
                table_roi = cv.resize(table_roi, (table.w * mult, table.h * mult))
                cv.imwrite(out + table_name, table_roi)

                num_img = 0
                for i in range(len(table_entries)):
                    row = table_entries[i]
                    for j in range(len(row)):
                        entry = row[j]
                        entry_roi = table_roi[entry[1] * mult: (entry[1] + entry[3]) * mult,
                                    entry[0] * mult:(entry[0] + entry[2]) * mult]

                        fname = out + "table/cell" + str(num_img) + ".jpg"
                        cv.imwrite(fname, entry_roi)

                        # fname = utils.run_textcleaner(fname, num_img)
                        text = utils.run_tesseract(fname, num_img, psm, oem)
                        num_img += 1
                        worksheet.write(i, j, text)
            workbook.close()
            filename = name
            download(filename)
            text = "Нажмите кнопку 'скачать текст', чтобы загрузить таблицу"
        else:
            text = ocr(filename)
            with open(f"text.txt", 'w') as text_file:
                text_file.write(text)
            if form == ".pdf":
                doc = aw.Document("text.txt")
                doc.save(fname + ".pdf")
                name = fname + '.pdf'
                os.replace('C:\\Users\\denis\\PycharmProjects\\Web\\'+name,
                           'C:\\Users\\denis\\PycharmProjects\\Web\\result\\'+name)
            elif form == ".docx":
                doc = aw.Document("text.txt")
                name = fname + ".docx"
                doc.save(name)
                os.replace('C:\\Users\\denis\\PycharmProjects\\Web\\'+name,
                           'C:\\Users\\denis\\PycharmProjects\\Web\\result\\'+name)
            os.renames("text.txt", fname + ".txt")
            name = fname + '.txt'
            os.replace('C:\\Users\\denis\\PycharmProjects\\Web\\'+name,
                       'C:\\Users\\denis\\PycharmProjects\\Web\\result\\'+name)
            filename = fname+form
            download(filename)
        return render_template('result.html', filename=filename, content=text)


@app.route('/result/<filename>', methods=['GET'])
def download(filename):
    return send_from_directory(app.config['RESULT_FOLDER'], filename)


def ocr(filename):
    global language, fname
    input_image = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img = cv.imread(input_image, cv.IMREAD_GRAYSCALE)
    img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    # img = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY)[1]
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(img, lang=language, config=custom_config)
    return text


def write_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    f = open("text.txt", "r")
    #x = open("text.pdf", "w", encoding="windows-1251")
    for x in f:
        pdf.cell(50, 10, txt=x, ln=1, align='C')
    pdf.output("text.pdf", 'F')


if __name__ == "__main__":
    app.run(debug=True)
