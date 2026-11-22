# -*- coding: utf-8 -*-
"""قراءة أسماء المواد من صورة (كاميرا أو معرض) على أندرويد.
المحرك: Tesseract (عربي + إنجليزي) بيشتغل على الجهاز من غير إنترنت. الملفات اللغوية في مجلد tessdata/
بتتنزّل وقت البناء (شوف .github/workflows/build-apk.yml).
مفيش إذن CAMERA بنطلبه — بنفتح تطبيق الكاميرا الأصلي، وبنحفظ الصورة مؤقتاً وبنمسحها بعد القراءة."""
import os
import threading
import time

from kivy.clock import Clock

HERE = os.path.dirname(os.path.abspath(__file__))
_REQ_CAM, _REQ_PICK = 7431, 7432
_lock = threading.Lock()
_api = None
_TESS_CLS = None      # بنحمّل كلاس Tesseract من الخيط الرئيسي (خيوط بايثون التانية مبتشوفش كلاسات التطبيق)


def is_android():
    try:
        from android import activity      # noqa
        from jnius import autoclass       # noqa
        return True
    except Exception:      # noqa
        return False


def _ac(name):
    from jnius import autoclass
    return autoclass(name)


def preload():
    """لازم تتنادي من الخيط الرئيسي: بتحمّل كلاس Tesseract عشان القراءة (اللي بتشتغل في خيط تاني) تلاقيه."""
    global _TESS_CLS
    if _TESS_CLS is None:
        try:
            _TESS_CLS = _ac('com.googlecode.tesseract.android.TessBaseAPI')
        except Exception:      # noqa
            _TESS_CLS = None


def _act():
    return _ac('org.kivy.android.PythonActivity').mActivity


def _sdk():
    return int(_ac('android.os.Build$VERSION').SDK_INT)


def _launch(intent, req, on_result):
    from android import activity

    def handler(rq, res, data):
        if rq != req:
            return
        try:
            activity.unbind(on_activity_result=handler)
        except Exception:      # noqa
            pass
        on_result(res, data)
    activity.bind(on_activity_result=handler)
    _act().startActivityForResult(intent, req)


def _later(fn, *a):
    Clock.schedule_once(lambda dt: fn(*a), 0)


def _delete(uri):
    try:
        _act().getContentResolver().delete(uri, None, None)
    except Exception:      # noqa
        pass


# ───────────── فتح الكاميرا / المعرض (cb(src, رسالة_خطأ)) ─────────────
def capture(cb):
    preload()

    def go():
        try:
            Intent = _ac('android.content.Intent')
            MS = _ac('android.provider.MediaStore')
            Media = _ac('android.provider.MediaStore$Images$Media')
            CV = _ac('android.content.ContentValues')
            cv = CV()
            cv.put('_display_name', 'murshid_%d.jpg' % int(time.time()))
            cv.put('mime_type', 'image/jpeg')
            if _sdk() >= 29:
                cv.put('relative_path', 'Pictures/Murshid')
            uri = _act().getContentResolver().insert(Media.EXTERNAL_CONTENT_URI, cv)
            it = Intent(MS.ACTION_IMAGE_CAPTURE)
            from jnius import cast
            it.putExtra(MS.EXTRA_OUTPUT, cast('android.os.Parcelable', uri))   # من غير cast بايجنيوس بيختار نسخة String غلط
            it.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION)

            def on_res(res, data):
                if res != -1:
                    _delete(uri)
                    _later(cb, None, '')
                else:
                    _later(cb, {'uri': uri, 'delete': True}, '')
            _launch(it, _REQ_CAM, on_res)
        except Exception as e:      # noqa
            _later(cb, None, 'تعذّر فتح الكاميرا: %s' % e)

    try:
        if _sdk() < 29:                      # أندرويد القديم محتاج إذن التخزين لحفظ الصورة
            from android.permissions import Permission, check_permission, request_permissions
            if not check_permission(Permission.WRITE_EXTERNAL_STORAGE):
                request_permissions([Permission.WRITE_EXTERNAL_STORAGE],
                                    lambda perms, grants: _later(go) if all(grants) else _later(cb, None, 'محتاج إذن التخزين عشان الكاميرا تحفظ الصورة.'))
                return
    except Exception:      # noqa
        pass
    go()


def pick(cb):
    preload()
    try:
        Intent = _ac('android.content.Intent')
        from jnius import cast
        String = _ac('java.lang.String')
        it = Intent(Intent.ACTION_GET_CONTENT)
        it.setType('image/*')
        it.addCategory(Intent.CATEGORY_OPENABLE)
        ch = Intent.createChooser(it, cast('java.lang.CharSequence', String('اختار صورة')))

        def on_res(res, data):
            if res != -1 or data is None or data.getData() is None:
                _later(cb, None, '')
            else:
                _later(cb, {'uri': data.getData(), 'delete': False}, '')
        _launch(ch, _REQ_PICK, on_res)
    except Exception as e:      # noqa
        _later(cb, None, 'تعذّر فتح المعرض: %s' % e)


# ───────────── تحميل الصورة (تصغير + تعديل الاتجاه) ─────────────
def _exif_rotation(res, uri):
    try:
        Ex = _ac('android.media.ExifInterface')
        s = res.openInputStream(uri)
        ori = int(Ex(s).getAttributeInt('Orientation', 1))
        s.close()
        return {6: 90, 3: 180, 8: 270}.get(ori, 0)
    except Exception:      # noqa
        return 0


def rotate(bmp, deg):
    M = _ac('android.graphics.Matrix')
    B = _ac('android.graphics.Bitmap')
    m = M()
    m.postRotate(float(deg))
    return B.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, True)


def load(src, max_side=2400):
    res = _act().getContentResolver()
    uri = src['uri']
    BF = _ac('android.graphics.BitmapFactory')
    Opt = _ac('android.graphics.BitmapFactory$Options')
    o = Opt()
    o.inJustDecodeBounds = True
    s = res.openInputStream(uri)
    BF.decodeStream(s, None, o)
    s.close()
    w, h = int(o.outWidth), int(o.outHeight)
    if w <= 0 or h <= 0:
        raise RuntimeError('مش قادر أقرأ الصورة دي.')
    ss = 1
    while max(w, h) / float(ss) > max_side:
        ss *= 2
    o2 = Opt()
    o2.inSampleSize = ss
    s = res.openInputStream(uri)
    bmp = BF.decodeStream(s, None, o2)
    s.close()
    if bmp is None:
        raise RuntimeError('مش قادر أفتح الصورة دي.')
    rot = _exif_rotation(res, uri)
    if rot:
        bmp = rotate(bmp, rot)
    if bmp.getWidth() < 1000:                     # صورة صغيرة: نكبّرها عشان القراءة تتحسّن
        B = _ac('android.graphics.Bitmap')
        bmp = B.createScaledBitmap(bmp, bmp.getWidth() * 2, bmp.getHeight() * 2, True)
    return bmp


def cleanup(src):
    if src and src.get('delete'):
        _delete(src['uri'])


# ───────────── القراءة (Tesseract) ─────────────
def _tess():
    global _api
    if _api is not None:
        return _api
    td = os.path.join(HERE, 'tessdata')
    if not os.path.exists(os.path.join(td, 'ara.traineddata')):
        raise RuntimeError('ملف اللغة العربي للقراءة مش موجود في التطبيق. اعمل بيلد جديد (خطوة تنزيل tessdata في GitHub Actions).')
    lang = 'ara+eng' if os.path.exists(os.path.join(td, 'eng.traineddata')) else 'ara'
    cls = _TESS_CLS
    if cls is None:
        try:
            cls = _ac('com.googlecode.tesseract.android.TessBaseAPI')
        except Exception:      # noqa
            raise RuntimeError('مكتبة القراءة (Tesseract) مش موجودة في الـAPK. اتأكد إن البيلد اتعمل بـ android.gradle_dependencies صح.')
    api = cls()
    if not api.init(HERE, lang):
        raise RuntimeError('تعذّر تشغيل محرك القراءة.')
    _api = api
    return api


def _ocr(bmp, psm):
    api = _tess()
    api.setPageSegMode(int(psm))
    api.setImage(bmp)
    txt = api.getUTF8Text()
    try:
        api.clear()
    except Exception:      # noqa
        pass
    return str(txt or '')


def _merge_lines(*texts):
    """يدمج نتايج أكتر من قراءة بدون تكرار السطور (عشان ولا مادة تضيع)."""
    seen, out = set(), []
    for t in texts:
        for ln in str(t).splitlines():
            k = ''.join(ln.split())
            if len(k) >= 3 and k not in seen:
                seen.add(k)
                out.append(ln)
    return '\n'.join(out)


def read_text(bmp, accept):
    """يقرأ النص بأكتر من نمط (صفحة كاملة / كتلة واحدة / أعمدة) ويدمجهم عشان كل المواد في الصورة تتقرأ.
    accept(نص) بترجّع درجة؛ لو الصورة مقلوبة/مايلة بيجرّب ٩٠ و٢٧٠ و١٨٠ لحد ما يلاقي مواد."""
    best, bs = '', -1.0
    with _lock:
        for rot in (0, 90, 270, 180):
            b = bmp if rot == 0 else rotate(bmp, rot)
            parts = []
            for psm in (3, 6, 4):
                try:
                    parts.append(_ocr(b, psm))
                except Exception:      # noqa
                    if not parts:
                        raise
            t = _merge_lines(*parts)
            s = accept(t)
            if s > bs:
                best, bs = t, s
            if s >= 1:
                break
    return best
