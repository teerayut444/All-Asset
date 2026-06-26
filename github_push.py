import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Path to the git executable on this machine
GIT_PATH = r"C:\Users\Teerayut.N\AppData\Local\Programs\Git\cmd\git.exe"

# Configure console encoding to avoid errors on Windows terminals
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def run_git_command(args, check=True):
    command = [GIT_PATH] + args
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=check, encoding='utf-8', errors='ignore')
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[-] เกิดข้อผิดพลาดขณะรันคำสั่ง git {' '.join(args)}")
        print(f"รายละเอียดข้อผิดพลาด:\n{e.stderr.strip() if e.stderr else 'ไม่มีรายละเอียด'}")
        if check:
            sys.exit(1)
        return None
    except FileNotFoundError:
        print(f"[-] ไม่พบโปรแกรม Git ที่พาธ: {GIT_PATH}")
        sys.exit(1)

def main():
    print("[System] เริ่มต้นระบบอัปโหลดไฟล์ขึ้น GitHub สำหรับ All Asset Dashboard...")
    
    # 1. Initialize git if not already done
    is_new_repo = False
    if not Path(".git").exists():
        print("[Git] ไม่พบโฟลเดอร์ .git กำลังเริ่มต้นระบบ Git Local...")
        run_git_command(["init"])
        run_git_command(["branch", "-M", "main"])
        is_new_repo = True
    
    # Check if remote origin already exists
    remotes = run_git_command(["remote", "-v"], check=False)
    has_origin = False
    if remotes and "origin" in remotes:
        has_origin = True
        
    if not has_origin:
        default_url = "https://github.com/teerayut444/All-Asset.git"
        print("\n[Git] ไม่พบการเชื่อมโยงกับ GitHub Repository (Remote 'origin')")
        print(f"ค่าเริ่มต้น: {default_url}")
        repo_url = input("กรุณากรอก GitHub URL ของคุณ (กด Enter เพื่อใช้ค่าเริ่มต้น): ").strip()
        if not repo_url:
            repo_url = default_url
        
        print(f"[Git] กำลังกำหนดค่า Remote ไปยัง: {repo_url}")
        run_git_command(["remote", "add", "origin", repo_url])
    else:
        # Show current remote
        lines = remotes.splitlines()
        for line in lines:
            if "(push)" in line:
                print(f"[Git] ตรวจพบ GitHub Remote: {line}")
                break

    # 2. Check status
    print("\n[Check] ตรวจสอบการเปลี่ยนแปลงไฟล์...")
    status = run_git_command(["status", "--porcelain"])
    
    # Check if there are untracked files or changes
    if not status:
        # If it's a new repo, we might still need to push initial setup
        # If not status, but it's new repo or has no commits, let's check commit count
        try:
            run_git_command(["rev-parse", "HEAD"], check=True)
            print("[Success] ไม่มีไฟล์ที่มีการเปลี่ยนแปลง ไม่จำเป็นต้อง commit")
            need_commit = False
        except SystemExit:
            # No commits yet
            need_commit = True
    else:
        need_commit = True

    if need_commit:
        if status:
            print("[Modified] ไฟล์ที่มีการเปลี่ยนแปลง/ไฟล์ใหม่:")
            for line in status.splitlines():
                print(f"  - {line}")
        else:
            print("[Info] ไม่มีไฟล์ที่มีการเปลี่ยนแปลง แต่อาจจะยังไม่มี Commit แรก")
        
        # 3. git add .
        print("\n[Git] กำลังสเตจไฟล์ (git add .)...")
        run_git_command(["add", "."])
        
        # 4. git commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto-update: {timestamp}"
        print(f"[Git] กำลังบันทึกประวัติการแก้ไข (git commit -m \"{commit_msg}\")...")
        commit_out = run_git_command(["commit", "-m", commit_msg])
        print(commit_out)
    
    # 5. git push origin main
    print("\n[Git] กำลังส่งข้อมูลขึ้น GitHub (git push -u origin main)...")
    print("โปรดรอสักครู่...")
    
    # If it is a new repo or we want to make sure the upstream is set
    push_args = ["push", "-u", "origin", "main"] if (is_new_repo or not has_origin) else ["push", "origin", "main"]
    run_git_command(push_args)
    print("\n[Success] อัปโหลดไฟล์และอัปเดตข้อมูลขึ้น GitHub สำเร็จเรียบร้อยแล้ว!")
    print("คุณสามารถนำไป Deploy บน Streamlit Cloud ได้ทันที")

if __name__ == "__main__":
    main()
