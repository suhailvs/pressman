## Pressman

#### Pages

1. location
2. add location
3. edit location
4. view location
5. map
6. pickups
7. pickup detail
8. staff
9. staff detail
10. add advance


#### Termux Setup in Android

Install missing build dependencies for Pillow and download the backup:
```bash
pkg update && pkg upgrade
pkg install python clang make libjpeg-turbo zlib freetype libpng
pkg install wget
pkg install unzip
cd mysite
wget https://pressman.pythonanywhere.com/backup/
rm -rf media
unzip index.html -d media
rm index.html
cd ..
pip install tzdata
python manage.py runserver
```