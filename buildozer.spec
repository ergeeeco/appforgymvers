[app]
title = Железный круг
package.name = ironcircle
package.domain = org.ironcircle
source.dir = .
source.include_exts = py,png,jpg,kv
version = 0.1
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,pillow,plyer,ffpyplayer
orientation = portrait
fullscreen = 0
icon.filename = icon-512.png
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
