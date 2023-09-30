import pytesseract
import cv2 as cv
import os
import aspose.words as aw
import uuid
import xlsxwriter
import numpy as np
from table import Table
from fpdf import FPDF
from PIL import Image
from flask import Flask, render_template, request, redirect, flash, send_from_directory


pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

UPLOAD_FOLDER = 'C:/Users/denis/PycharmProjects/Web1/uploads'
RESULT_FOLDER = 'C:/Users/denis/PycharmProjects/Web1/result'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
MAX_THRESHOLD_VALUE = 255
BLOCK_SIZE = 15
THRESHOLD_CONSTANT = 0
MIN_TABLE_AREA = 50
EPSILON = 3
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
            filename, file_extension = os.path.splitext(file.filename)
            fname = str(uuid.uuid4())
            filename = fname + file_extension
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect('/process/' + filename)
    return render_template('index.html')


@app.route('/process/<filename>', methods=['GET'])
def processing(filename):
    global form, fname
    if request.method == 'GET':
        if form == ".xlsx":
            image = cv.imread('uploads/' + filename)
            grayscale = cv.cvtColor(image, cv.COLOR_RGB2GRAY)
            filtered = cv.adaptiveThreshold(~grayscale, MAX_THRESHOLD_VALUE, cv.ADAPTIVE_THRESH_MEAN_C,
                                            cv.THRESH_BINARY, BLOCK_SIZE, THRESHOLD_CONSTANT)
            SCALE = 15
            horizontal = filtered.copy()
            vertical = filtered.copy()

            horizontal_size = int(horizontal.shape[1] / SCALE)
            horizontal_structure = cv.getStructuringElement(cv.MORPH_RECT, (horizontal_size, 1))
            isolate_lines(horizontal, horizontal_structure)

            vertical_size = int(vertical.shape[0] / SCALE)
            vertical_structure = cv.getStructuringElement(cv.MORPH_RECT, (1, vertical_size))
            isolate_lines(vertical, vertical_structure)

            mask = horizontal + vertical
            (contours, _) = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            intersections = cv.bitwise_and(horizontal, vertical)


            tables = []
            for i in range(len(contours)):
                (rect, table_joints) = verify_table(contours[i], intersections)
                if rect == None or table_joints == None:
                    continue

                table = Table(rect[0], rect[1], rect[2], rect[3])
                joint_coords = []

                for i in range(len(table_joints)):
                    joint_coords.append(table_joints[i][0][0])

                joint_coords = np.asarray(joint_coords)
                sorted_indices = np.lexsort((joint_coords[:, 0], joint_coords[:, 1]))
                joint_coords = joint_coords[sorted_indices]

                table.set_joints(joint_coords)
                tables.append(table)

            out = "bin/"
            table_name = "table.jpg"
            psm = 10
            oem = 3
            mult = 3
            name = fname + '.xlsx'
            workbook = xlsxwriter.Workbook('result/' + name)

            for table in tables:
                worksheet = workbook.add_worksheet()

                table_entries = table.get_table_entries()

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
                        text = run_tesseract(fname, num_img, psm, oem)
                        num_img += 1
                        worksheet.write(i, j, text)
            workbook.close()
            filename = name
            download(filename)
            text = 'Нажмите кнопку "Скачать текст", чтобы загрузить таблицу'
        else:
            text = ocr(filename)
            with open(f"text.txt", 'w') as text_file:
                text_file.write(text)
            if form == ".pdf":
                doc = aw.Document("text.txt")
                doc.save(fname + ".pdf")
                name = fname + '.pdf'
                os.replace('C:\\Users\\denis\\PycharmProjects\\Web1\\' + name,
                           'C:\\Users\\denis\\PycharmProjects\\Web1\\result\\' + name)
            elif form == ".docx":
                doc = aw.Document("text.txt")
                doc.save(fname + ".docx")
                name = fname + ".docx"
                os.replace('C:\\Users\\denis\\PycharmProjects\\Web1\\' + name,
                           'C:\\Users\\denis\\PycharmProjects\\Web1\\result\\' + name)
            os.renames("text.txt", fname + ".txt")
            name = fname + '.txt'
            os.replace('C:\\Users\\denis\\PycharmProjects\\Web1\\' + name,
                       'C:\\Users\\denis\\PycharmProjects\\Web1\\result\\' + name)
            filename = fname + form
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
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(img, lang=language, config=custom_config)
    return text


def run_tesseract(filename, psm, oem):
    global language
    image = Image.open(filename)
    configuration = "--psm " + str(psm) + " --oem " + str(oem)
    text = pytesseract.image_to_string(image, lang=language, config=configuration)
    if len(text.strip()) == 0:
        text = pytesseract.image_to_string(image, lang=language, config=configuration)
    return text


def showImg(name, matrix, durationMillis=0):
    cv.imshow(name, matrix)
    cv.waitKey(durationMillis)


def isolate_lines(src, structuring_element):
    cv.erode(src, structuring_element, src, (-1, -1))
    cv.dilate(src, structuring_element, src, (-1, -1))


def mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def verify_table(contour, intersections):
    area = cv.contourArea(contour)

    if area < MIN_TABLE_AREA:
        return None, None

    curve = cv.approxPolyDP(contour, EPSILON, True)
    rect = cv.boundingRect(curve)  # format of each rect: x, y, w, h

    # Находит количество стыков в каждой интересующей области
    # Формат находится в порядке строк-столбцов (поскольку поиск области включает массивы numpy)
    # формат: image_mat[rect.y: rect.y + rect.h, rect.x: rect.x + rect.w]
    possible_table_region = intersections[rect[1]:rect[1] + rect[3], rect[0]:rect[0] + rect[2]]
    (possible_table_joints, _) = cv.findContours(possible_table_region, cv.RETR_CCOMP, cv.CHAIN_APPROX_SIMPLE)

    # Определяет количество стыков таблицы в изображении
    # Если менее 5 стыков в таблице, то изображение не таблица
    if len(possible_table_joints) < 5:
        return None, None

    return rect, possible_table_joints


def write_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    f = open("text.txt", "r")
    for x in f:
        pdf.cell(50, 10, txt=x, ln=1, align='C')
    pdf.output("text.pdf", 'F')


if __name__ == "__main__":
    app.run(debug=True)
