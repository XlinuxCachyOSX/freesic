#!/bin/sh
# Compila l'APK Android di FreeSic.
#
#   ./build-apk.sh              -> dist/FreeSic-1.0.0.apk
#
# Scarica e usa JDK 17, Android SDK e Gradle in ~/android-toolchain
# (nessuna installazione di sistema richiesta).
set -e

PROGETTO="$(cd "$(dirname "$0")" && pwd)"
BASE="${ANDROID_TOOLCHAIN:-$HOME/android-toolchain}"
SDK="$BASE/android-sdk"
mkdir -p "$BASE" && cd "$BASE"

if [ ! -x "$BASE/jdk/bin/java" ]; then
  echo "== JDK 17 =="
  curl -sSL -o jdk.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
  mkdir -p jdk && tar -xzf jdk.tar.gz -C jdk --strip-components=1
fi

if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
  echo "== Android command line tools =="
  curl -sSL -o cmdline.zip "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  mkdir -p cmdline-tools && unzip -q cmdline.zip -d cmdline-tools && mv cmdline-tools/cmdline-tools cmdline-tools/latest
  mkdir -p "$SDK" && rm -rf "$SDK/cmdline-tools" && mv cmdline-tools "$SDK/cmdline-tools"
fi

export JAVA_HOME="$BASE/jdk"
export ANDROID_HOME="$SDK"
export PATH="$JAVA_HOME/bin:$SDK/cmdline-tools/latest/bin:$PATH"

if [ ! -d "$SDK/platforms/android-34" ]; then
  echo "== platform e build-tools =="
  yes | sdkmanager --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
  sdkmanager --sdk_root="$SDK" "platforms;android-34" "build-tools;34.0.0" "platform-tools" >/dev/null
fi

if [ ! -x "$BASE/gradle/bin/gradle" ] && [ ! -x "$BASE/gradle-8.7/bin/gradle" ]; then
  echo "== Gradle =="
  curl -sSL -o gradle.zip "https://services.gradle.org/distributions/gradle-8.7-bin.zip"
  unzip -q gradle.zip && rm gradle.zip
  ln -sfn "$BASE/gradle-8.7" "$BASE/gradle"
fi

GRADLE="$BASE/gradle/bin/gradle"
[ -x "$GRADLE" ] || GRADLE="$BASE/gradle-8.7/bin/gradle"

cd "$PROGETTO"
echo "sdk.dir=$SDK" > local.properties

echo "== build =="
"$GRADLE" --no-daemon assembleRelease assembleDebug

mkdir -p "$PROGETTO/../dist"
VERSIONE=$(sed -nE 's/.*versionName "([^"]+)".*/\1/p' app/build.gradle | head -1)
cp app/build/outputs/apk/release/app-release.apk "$PROGETTO/../dist/FreeSic-$VERSIONE.apk"
cp app/build/outputs/apk/debug/app-debug.apk "$PROGETTO/../dist/FreeSic-debug.apk"

echo ""
echo "APK pronto:"
ls -lh "$PROGETTO/../dist"
