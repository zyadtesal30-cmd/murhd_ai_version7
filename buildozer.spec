[app]
# مهم: لازم يفضل هنا تحت [app] — بيثبّت نسخة python-for-android (من غيره البيلد بيفشل)
p4a.branch = v2024.01.21

title = Murshid Al-Talib
package.name = murshidtalib
package.domain = org.zyadtarek
version = 1.0.0

source.dir = .
source.include_exts = py,png,jpg,ttf,traineddata
source.include_patterns = fonts/*,assets/*,tessdata/*
source.exclude_dirs = .github,bin,.buildozer,tools

# إصدارات مثبّتة: بايثون 3.11.5 للتطبيق وللبناء (لازم يتطابقوا)
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,python-bidi==0.4.2,six,setuptools,pyjnius,android,certifi

orientation = portrait

# الأيقونة (متكيفة مع أندرويد الحديث) وشاشة البداية
icon.filename = %(source.dir)s/assets/icon.png
icon.adaptive_foreground.filename = %(source.dir)s/assets/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/icon_bg.png
presplash.filename = %(source.dir)s/assets/presplash.png
presplash.color = #0B0F19
fullscreen = 0

android.archs = arm64-v8a
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True
# لا نضيف CAMERA عمداً: لو اتعلنت ولم تتمنح، فتح الكاميرا بيفشل. بنفتح تطبيق الكاميرا الأصلي.
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE
android.enable_androidx = True
# Tesseract4Android بيتوزّع عن طريق JitPack (مش Maven Central ولا google) — لازم نضيف مستودع JitPack.
# بنكتبه من غير علامات تنصيص خارجية (buildozer بيمرّرها حرفياً لـgradle).
# لو JitPack رجّع 404 في أول مرة (بيبني المكتبة عند أول طلب) أعد تشغيل الـworkflow بعد دقيقتين.
android.add_gradle_repositories = maven { url 'https://jitpack.io' }
android.gradle_dependencies = cz.adaptech.tesseract4android:tesseract4android:4.5.0
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
