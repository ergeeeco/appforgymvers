[app]
title = Железный круг
package.name = ironcircle
package.domain = org.ironcircle
source.dir = .
source.exclude_dirs = tests, bin, venv, icons_src, tools, docs
source.include_exts = py,png,jpg,kv,ttf,json
version = 0.1
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,pillow,plyer,androidstorage4kivy
orientation = portrait
fullscreen = 0
icon.filename = icon-512.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0c150e
# Анимированная заставка (вращающаяся гантель). Раскомментируйте, если сборка с Lottie проходит:
#presplash.lottie = %(source.dir)s/presplash.lottie
android.permissions = INTERNET,POST_NOTIFICATIONS
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.enable_androidx = True
android.ndk = 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
