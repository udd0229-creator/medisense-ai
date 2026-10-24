#!/usr/bin/env bash
# Builds MediSense_AI.apk without Gradle, using the Android SDK tools packaged by Ubuntu:
#   sudo apt install android-sdk-platform-23 aapt dalvik-exchange zipalign apksigner openjdk-17-jdk
set -euo pipefail
cd "$(dirname "$0")"
ANDROID_JAR=${ANDROID_JAR:-/usr/lib/android-sdk/platforms/android-23/android.jar}
rm -rf build && mkdir -p build/gen build/obj build/apk

# 1. compile resources + manifest, generate R.java
aapt package -f -m -J build/gen -M AndroidManifest.xml -S res -I "$ANDROID_JAR" \
     -F build/apk/app.unsigned.apk

# 2. compile Java (Java 8 bytecode for the dex tool)
javac -nowarn -source 8 -target 8 -bootclasspath "$ANDROID_JAR" -d build/obj \
      $(find src build/gen -name '*.java')

# 3. convert to Dalvik bytecode
dalvik-exchange --dex --min-sdk-version=24 --output=build/apk/classes.dex build/obj

# 4. add classes.dex to the APK, align, sign
(cd build/apk && aapt add app.unsigned.apk classes.dex >/dev/null)
zipalign -f -p 4 build/apk/app.unsigned.apk build/apk/app.aligned.apk
if [ ! -f medisense.keystore ]; then
  keytool -genkeypair -v -keystore medisense.keystore -alias medisense -keyalg RSA -keysize 2048 \
          -validity 10000 -storepass medisense123 -keypass medisense123 \
          -dname "CN=MediSense AI, OU=BCA Project, O=BIT Mesra Patna, L=Patna, ST=Bihar, C=IN"
fi
apksigner sign --ks medisense.keystore --ks-key-alias medisense \
     --ks-pass pass:medisense123 --key-pass pass:medisense123 \
     --out MediSense_AI.apk build/apk/app.aligned.apk
apksigner verify --verbose MediSense_AI.apk
echo "Built $(pwd)/MediSense_AI.apk"
