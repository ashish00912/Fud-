import os
import subprocess
import shutil
import random
import string
import tempfile
import re
import urllib.request
import stat

class APKObfuscator:
    APKTOOL_URL = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar"
    
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path
        self.work_dir = tempfile.mkdtemp(prefix="apk_obf_")
        self.decompiled_dir = os.path.join(self.work_dir, "decompiled")
        self.keystore_path = os.path.join(self.work_dir, "test.keystore")
        self.apktool_jar = os.path.join(self.work_dir, "apktool.jar")
        self._ensure_apktool()

    def _ensure_apktool(self):
        """Download apktool.jar if not already present."""
        if not os.path.exists(self.apktool_jar):
            print("📥 Downloading apktool.jar...")
            try:
                urllib.request.urlretrieve(self.APKTOOL_URL, self.apktool_jar)
                # Make executable (not needed for jar but fine)
                os.chmod(self.apktool_jar, os.stat(self.apktool_jar).st_mode | stat.S_IEXEC)
                print("✅ apktool.jar downloaded.")
            except Exception as e:
                raise Exception(f"Failed to download apktool: {e}")

    def _get_apktool_cmd(self, action, *args):
        """Return the command to run apktool (either system or jar)."""
        # Try system apktool first
        if shutil.which("apktool"):
            cmd = ["apktool", action] + list(args)
        else:
            # Use java -jar
            cmd = ["java", "-jar", self.apktool_jar, action] + list(args)
        return cmd

    def decompile(self):
        os.makedirs(self.decompiled_dir, exist_ok=True)
        cmd = self._get_apktool_cmd("d", self.input_path, "-o", self.decompiled_dir, "-f")
        subprocess.run(cmd, check=True)
        return self.decompiled_dir

    def obfuscate_smali(self):
        smali_dir = os.path.join(self.decompiled_dir, "smali")
        for root, _, files in os.walk(smali_dir):
            for file in files:
                if file.endswith(".smali"):
                    path = os.path.join(root, file)
                    self._obfuscate_smali_file(path)

    def _obfuscate_smali_file(self, path):
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.strip().startswith('.method'):
                if 'onCreate' not in line and 'onStart' not in line:
                    line = line.replace('onCreate', f'on{random.randint(1000,9999)}')
            if ';->' in line:
                parts = line.split(';->')
                if len(parts) > 1:
                    meth = parts[1].split('(')[0]
                    if meth not in ['<init>', 'toString', 'equals']:
                        line = line.replace(meth, ''.join(random.choices(string.ascii_lowercase, k=8)))
            new_lines.append(line)
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    def obfuscate_strings(self):
        smali_dir = os.path.join(self.decompiled_dir, "smali")
        for root, _, files in os.walk(smali_dir):
            for file in files:
                if file.endswith(".smali"):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    def replacer(match):
                        original = match.group(1)
                        hex_str = ''.join([hex(ord(c))[2:].zfill(2) for c in original])
                        return f'"{hex_str}"'
                    content = re.sub(r'"([^"]*)"', replacer, content)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)

    def add_anti_debug(self):
        main_smali = self._find_main_activity_smali()
        if main_smali:
            with open(main_smali, 'a', encoding='utf-8') as f:
                f.write('''
.method static constructor <clinit>()V
    .registers 2
    const-string v0, "android.os.Debug"
    invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
    move-result-object v0
    const-string v1, "isDebuggerConnected"
    invoke-virtual {v0, v1}, Ljava/lang/Class;->getMethod(Ljava/lang/String;)Ljava/lang/reflect/Method;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/reflect/Method;->invoke()Ljava/lang/Object;
    move-result-object v0
    invoke-static {v0}, Ljava/lang/Boolean;->parseBoolean(Ljava/lang/String;)Z
    move-result v0
    if-nez v0, :cond_1
    :cond_1
    return-void
.end method
''')

    def _find_main_activity_smali(self):
        manifest_path = os.path.join(self.decompiled_dir, "AndroidManifest.xml")
        with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        match = re.search(r'<activity[^>]*android:name="([^"]+)"[^>]*>', content)
        if match:
            main_activity = match.group(1).replace('.', '/')
            smali_path = os.path.join(self.decompiled_dir, "smali", main_activity + ".smali")
            if os.path.exists(smali_path):
                return smali_path
        return None

    def rebuild(self):
        cmd = self._get_apktool_cmd("b", self.decompiled_dir, "-o", self.output_path, "-f")
        subprocess.run(cmd, check=True)

    def _ensure_keystore(self):
        if not os.path.exists(self.keystore_path):
            cmd = (
                f"keytool -genkey -v -keystore {self.keystore_path} "
                f"-alias test -keyalg RSA -keysize 2048 -validity 10000 "
                f"-storepass android -keypass android "
                f"-dname 'CN=Test, OU=Test, O=Test, L=Test, ST=Test, C=IN'"
            )
            subprocess.run(cmd, shell=True, check=True, stderr=subprocess.DEVNULL)

    def sign_apk(self):
        self._ensure_keystore()
        try:
            # Try apksigner if available
            if shutil.which("apksigner"):
                cmd = (
                    f"apksigner sign --ks {self.keystore_path} "
                    f"--ks-pass pass:android --key-pass pass:android "
                    f"--out {self.output_path}_signed.apk {self.output_path}"
                )
                subprocess.run(cmd, shell=True, check=True)
                shutil.move(f"{self.output_path}_signed.apk", self.output_path)
            else:
                raise Exception("apksigner not found")
        except Exception:
            # Fallback to jarsigner (always available with Java)
            cmd = (
                f"jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 "
                f"-keystore {self.keystore_path} -storepass android -keypass android "
                f"{self.output_path} test"
            )
            subprocess.run(cmd, shell=True, check=True)
            # zipalign optional, but try if available
            if shutil.which("zipalign"):
                cmd = f"zipalign -v -p 4 {self.output_path} {self.output_path}_aligned.apk"
                subprocess.run(cmd, shell=True, check=True)
                shutil.move(f"{self.output_path}_aligned.apk", self.output_path)

    def run(self):
        self.decompile()
        self.obfuscate_smali()
        self.obfuscate_strings()
        self.add_anti_debug()
        self.rebuild()
        self.sign_apk()
        shutil.rmtree(self.work_dir, ignore_errors=True)
        return self.output_path
