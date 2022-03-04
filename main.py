import pytesseract
import cv2

pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

img = cv2.imread('image.jpg', cv2.IMREAD_GRAYSCALE)
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
#img = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY)[1]

custom_config = r'--oem 3 --psm 6'

text = pytesseract.image_to_string(img, lang='rus', config=custom_config)
print(text)

with open(f'text.txt', 'w') as text_file:
    text_file.write(text)

cv2.imshow('Result', img)
cv2.waitKey(0)