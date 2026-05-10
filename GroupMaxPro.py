import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import re
import pandas as pd
import os
from pathlib import Path
import sys
import requests
import hashlib
import uuid
import platform
import getpass
from datetime import datetime, date, timedelta, timezone
import webbrowser
from collections import defaultdict
import json

# ==================== BIẾN TOÀN CỤC ====================
last_exported_file = None
item_map = defaultdict(list)
last_profit = 0.0

DEBT_FILE = Path("cong_no.json")
REVENUE_FILE = Path("doanh_thu.json")
debt_list = []
revenue_list = []

LICENSE_FILE = Path("license.key")
API_URL = "https://create-account-vtc.up.railway.app/api/check-license"
PRICING_URL = "https://create-account-vtc.up.railway.app/pricing"

# ==================== DATE SELECTOR ====================
class DateSelector(tk.Frame):
    def __init__(self, parent, default_date=None):
        super().__init__(parent, bg="#f8f9fa")
        self.day_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.year_var = tk.StringVar()

        self.day_cb = ttk.Combobox(self, textvariable=self.day_var, width=4, state="readonly")
        self.day_cb['values'] = [f"{i:02d}" for i in range(1, 32)]
        self.day_cb.grid(row=0, column=0, padx=2)

        self.month_cb = ttk.Combobox(self, textvariable=self.month_var, width=4, state="readonly")
        self.month_cb['values'] = [f"{i:02d}" for i in range(1, 13)]
        self.month_cb.grid(row=0, column=1, padx=2)

        self.year_cb = ttk.Combobox(self, textvariable=self.year_var, width=6, state="readonly")
        self.year_cb['values'] = [str(i) for i in range(2020, 2036)]
        self.year_cb.grid(row=0, column=2, padx=2)

        if default_date is None:
            default_date = date.today()
        self.set_date(default_date)

    def get_date(self):
        try:
            return date(int(self.year_var.get()), int(self.month_var.get()), int(self.day_var.get()))
        except:
            return date.today()

    def set_date(self, dt):
        if isinstance(dt, str):
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d").date()
            except:
                dt = date.today()
        self.day_var.set(f"{dt.day:02d}")
        self.month_var.set(f"{dt.month:02d}")
        self.year_var.set(str(dt.year))

    def get_date_str(self):
        return self.get_date().strftime("%Y-%m-%d")

# ==================== LICENSE SYSTEM ====================
# ==================== LICENSE SYSTEM (ĐÃ FIX) ====================
def get_hwid():
    try:
        info = (platform.node() + str(uuid.getnode()) + platform.processor() +
                getpass.getuser() + platform.machine() + platform.system())
        return hashlib.sha256(info.encode('utf-8')).hexdigest().upper()[:32]
    except:
        return "ERROR-HWID"

def verify_license_online(key):
    hwid = get_hwid()
    try:
        response = requests.post(API_URL, json={"license_key": key, "hwid": hwid}, timeout=12)
        if response.status_code != 200:
            return False, 0, f"Server lỗi {response.status_code}"

        data = response.json()

        # === DEBUG (bạn có thể comment 2 dòng này sau khi test xong) ===
        # print("=== SERVER RESPONSE ===")
        # print(data)

        if not data.get("valid"):
            return False, 0, data.get("message", "Key không hợp lệ")

        # Ưu tiên cao nhất: remaining_days (giống file cũ của bạn)
        if "remaining_days" in data:
            days = int(data.get("remaining_days", 0))
            if days > 0:
                save_license(key)
                return True, days, f"Còn {days} ngày"
            elif days == 0:
                return False, 0, "❌ License đã hết hạn"

        # Hỗ trợ key vĩnh viễn
        if data.get("is_permanent") is True or data.get("license", {}).get("is_permanent") is True:
            save_license(key)
            return True, 99999, "Vĩnh viễn"

        # Fallback: parse expiry (hỗ trợ cả nested "license" lẫn root)
        license_obj = data.get("license", data)
        expiry_str = license_obj.get("expiry", data.get("expiry", "")).strip()

        if expiry_str:
            try:
                if expiry_str.endswith("Z"):
                    expiry_str = expiry_str[:-1] + "+00:00"
                expiry = datetime.fromisoformat(expiry_str)
                days_left = (expiry.date() - date.today()).days
                if days_left > 0:
                    save_license(key)
                    return True, days_left, f"Còn {days_left} ngày"
                else:
                    return False, 0, "❌ License đã hết hạn"
            except:
                pass

        # Nếu không có ngày hết hạn rõ ràng → vẫn coi là hợp lệ
        save_license(key)
        return True, 99999, "Hợp lệ (không giới hạn ngày)"

    except Exception as e:
        return False, -1, f"Lỗi kết nối server: {str(e)[:100]}"
def load_license_info():
    if LICENSE_FILE.exists():
        try:
            with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
                key = f.read().strip()
            if key.upper().startswith("VTC-"):
                return verify_license_online(key)
        except:
            pass
    return False, 0, None

def save_license(key):
    try:
        with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
            f.write(key.strip().upper())
        return True
    except:
        return False

def update_title(valid, status_text):
    if valid:
        root.title(f"Tool Ghép Nhóm + Tính Sale + Lợi Nhuận Sale Game v2.0 - by Hoàng Phú - Hợp lệ - {status_text}")
    else:
        root.title("Tool Ghép Nhóm + Tính Sale + Lợi Nhuận Sale Game v2.0 - by Hoàng Phú - License không hợp lệ")

# ==================== GIAO DIỆN NHẬP KEY ĐẸP (từ file cũ của bạn) ====================
def show_license_dialog():
    dialog = tk.Tk()
    dialog.title("🔑 KÍCH HOẠT LICENSE - Tool Ghép Nhóm v2.0")
    dialog.geometry("700x520")
    dialog.configure(bg="#2c3e50")
    dialog.resizable(False, False)

    hwid = get_hwid()
    tk.Label(dialog, text="🔑 KÍCH HOẠT BẢN QUYỀN", font=("Arial", 18, "bold"), fg="#2ecc71", bg="#2c3e50").pack(pady=15)
    tk.Label(dialog, text="HWID của máy bạn:", font=("Arial", 11, "bold"), fg="#f1c40f", bg="#2c3e50").pack(anchor="w", padx=40)
    tk.Label(dialog, text=hwid, font=("Consolas", 11), fg="#e74c3c", bg="#34495e", width=62, height=2, relief="sunken").pack(pady=8, padx=40)
    tk.Label(dialog, text="Dán License Key từ Dashboard VTC:", font=("Arial", 12, "bold"), fg="white", bg="#2c3e50").pack(anchor="w", padx=40, pady=(10,5))

    entry_key = tk.Entry(dialog, font=("Consolas", 14), width=50, justify="center")
    entry_key.pack(pady=8, padx=40, ipady=8)

    def activate():
        key = entry_key.get().strip().upper()
        if not key.startswith("VTC-"):
            messagebox.showerror("❌ Sai key", "Key phải bắt đầu bằng VTC-", parent=dialog)
            return
        valid, remaining, status_text = verify_license_online(key)
        if valid:
            save_license(key)
            messagebox.showinfo("✅ THÀNH CÔNG", f"License hợp lệ!\nKey: {key}\n{status_text}", parent=dialog)
            dialog.destroy()
            update_title(valid, status_text)
            root.deiconify()
            check_overdue_reminder()
        else:
            messagebox.showerror("❌ Không hợp lệ", status_text, parent=dialog)

    def reset_license():
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
            messagebox.showinfo("Reset", "Đã xóa license cũ.", parent=dialog)

    def open_pricing():
        webbrowser.open(PRICING_URL)

    btn_frame = tk.Frame(dialog, bg="#2c3e50")
    btn_frame.pack(pady=20)
    tk.Button(btn_frame, text="🌐 MUA LICENSE KEY NGAY", command=open_pricing,
              bg="#f39c12", fg="white", font=("Arial", 12, "bold"), width=30, height=2).pack(pady=8)
    tk.Button(btn_frame, text="🚀 KÍCH HOẠT", command=activate, bg="#27ae60", fg="white", font=("Arial", 13, "bold"), width=20, height=2).pack(side="left", padx=10)
    tk.Button(btn_frame, text="🔄 Reset License", command=reset_license, bg="#f39c12", fg="white", font=("Arial", 13, "bold"), width=18, height=2).pack(side="left", padx=10)
    tk.Button(btn_frame, text="❌ Thoát", command=sys.exit, bg="#e74c3c", fg="white", font=("Arial", 13, "bold"), width=15, height=2).pack(side="left", padx=10)

    tk.Label(dialog, text="© 2026 - by Hoàng Phú\n1 key dùng chung nhiều tool - Lock theo 1 máy", 
             font=("Arial", 9), fg="#95a5a6", bg="#2c3e50").pack(side="bottom", pady=15)
    dialog.mainloop()
# ==================== MONEY & HELPER ====================
def format_money(amount):
    if amount == int(amount):
        return f"{int(amount):,}".replace(',', '.') + " VNĐ"
    else:
        return f"{amount:,.2f}".replace(',', '.') + " VNĐ"

def parse_money(text):
    if not text or text.strip() == "": return 0.0
    cleaned = text.replace('.', '').replace(',', '')
    try:
        return float(cleaned)
    except:
        return 0.0

def get_days_debt(ngay_no_str):
    try:
        ngay_no = datetime.strptime(ngay_no_str, "%Y-%m-%d").date()
        return (date.today() - ngay_no).days
    except:
        return 0

# ==================== NHẮC CÔNG NỢ ====================
def check_overdue_reminder():
    load_debt_data()
    overdue_count = sum(1 for d in debt_list if (d["so_tien_no"] - d.get("da_thanh_toan", 0)) > 0 and get_days_debt(d.get("ngay_no", "")) > 10)
    if overdue_count > 0:
        show_custom_reminder(overdue_count)

def show_custom_reminder(count):
    dialog = tk.Toplevel(root)
    dialog.title("⚠️ NHẮC NHỞ CÔNG NỢ QUÁ HẠN")
    dialog.geometry("560x320")
    dialog.configure(bg="#fff3cd")
    dialog.grab_set()
    dialog.resizable(False, False)
    tk.Label(dialog, text="⚠️", font=("Arial", 80), bg="#fff3cd", fg="#d32f2f").pack(pady=10)
    tk.Label(dialog, text="CÔNG NỢ QUÁ HẠN!", font=("Arial", 18, "bold"), bg="#fff3cd", fg="#d32f2f").pack()
    msg = f"Bạn đang có **{count}** khoản công nợ quá hạn (>10 ngày)\nCần báo thanh toán ngay!"
    tk.Label(dialog, text=msg, font=("Arial", 14, "bold"), bg="#fff3cd", fg="#333333", justify="center", wraplength=500).pack(pady=15)
    tk.Button(dialog, text="ĐÃ HIỂU", command=dialog.destroy, bg="#d32f2f", fg="white", font=("Arial", 14, "bold"), width=20, height=2).pack(pady=20)

# ==================== MINI CALCULATOR ====================
class MiniCalculator:
    def __init__(self, parent):
        self.frame = tk.LabelFrame(parent, text="🧮 Máy Tính Nhanh", font=("Arial", 11, "bold"), bg="#f8f9fa", padx=10, pady=10)
        self.display = tk.Entry(self.frame, font=("Consolas", 16, "bold"), justify="right", state="readonly", width=20)
        self.display.grid(row=0, column=0, columnspan=4, sticky="ew", pady=8)
        self.current = ""
        self.create_buttons()

    def create_buttons(self):
        buttons = ['7','8','9','/','4','5','6','*','1','2','3','-','0','.','C','+']
        row, col = 1, 0
        for btn in buttons:
            if btn == 'C':
                tk.Button(self.frame, text=btn, font=("Arial", 14, "bold"), bg="#ff9800", fg="white", width=5, command=self.clear).grid(row=row, column=col, padx=3, pady=3)
            else:
                tk.Button(self.frame, text=btn, font=("Arial", 14, "bold"), bg="#f0f0f0", width=5, command=lambda x=btn: self.on_button_click(x)).grid(row=row, column=col, padx=3, pady=3)
            col += 1
            if col > 3:
                col = 0
                row += 1
        tk.Button(self.frame, text="=", font=("Arial", 14, "bold"), bg="#4CAF50", fg="white", width=22, command=self.calculate).grid(row=row, column=0, columnspan=4, pady=6)

    def on_button_click(self, char):
        self.current += str(char)
        self.display.config(state="normal")
        self.display.delete(0, tk.END)
        self.display.insert(0, self.current)
        self.display.config(state="readonly")

    def clear(self):
        self.current = ""
        self.display.config(state="normal")
        self.display.delete(0, tk.END)
        self.display.config(state="readonly")

    def calculate(self):
        try:
            result = eval(self.current)
            self.current = str(result)
            self.display.config(state="normal")
            self.display.delete(0, tk.END)
            self.display.insert(0, self.current)
            self.display.config(state="readonly")
        except:
            self.current = "Lỗi"
            self.display.config(state="normal")
            self.display.delete(0, tk.END)
            self.display.insert(0, self.current)
            self.display.config(state="readonly")

def open_calculator():
    calc_win = tk.Toplevel(root)
    calc_win.title("🧮 Máy Tính Nhanh")
    calc_win.geometry("360x420")
    calc_win.configure(bg="#f8f9fa")
    calc_win.resizable(False, False)
    MiniCalculator(calc_win).frame.pack(padx=15, pady=15, fill="both", expand=True)

# ==================== GHI DOANH THU ====================
def record_profit_to_revenue():
    global last_profit
    if last_profit <= 0:
        messagebox.showwarning("Chưa có lợi nhuận", "Vui lòng bấm **TÍNH TOÁN** trước!")
        return
    today = date.today().strftime("%Y-%m-%d")
    revenue_list.append({"ngay": today, "doanh_thu": last_profit, "ghi_chu": "Lợi nhuận từ Sale Game"})
    save_revenue_data()
    messagebox.showinfo("✅ ĐÃ GHI", f"Đã ghi nhận **{format_money(last_profit)}** vào Doanh Thu")
    open_revenue_window()

# ==================== QUẢN LÝ DOANH THU & CÔNG NỢ ====================
def load_revenue_data():
    global revenue_list
    if REVENUE_FILE.exists():
        try:
            with open(REVENUE_FILE, 'r', encoding='utf-8') as f:
                revenue_list = json.load(f)
        except:
            revenue_list = []
    else:
        revenue_list = []

def save_revenue_data():
    try:
        with open(REVENUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(revenue_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Lỗi", f"Lỗi lưu doanh thu: {str(e)}")

def refresh_revenue_tree(tree, total_label, from_date=None, to_date=None):
    for item in tree.get_children():
        tree.delete(item)
    filtered = revenue_list
    if from_date and to_date:
        filtered = [r for r in revenue_list if from_date <= datetime.strptime(r["ngay"], "%Y-%m-%d").date() <= to_date]
    filtered = sorted(filtered, key=lambda x: x["ngay"], reverse=True)
    total = 0
    for i, rev in enumerate(filtered, 1):
        amount = rev.get("doanh_thu", 0)
        total += amount
        tree.insert("", "end", values=(i, rev.get("ngay", ""), format_money(amount), rev.get("ghi_chu", "")[:40]))
    total_label.config(text=f"💰 TỔNG DOANH THU: {format_money(total)}")

def open_revenue_window():
    rev_win = tk.Toplevel(root)
    rev_win.title("📊 Quản Lý Doanh Thu")
    rev_win.geometry("1100x720")
    rev_win.configure(bg="#f8f9fa")
    rev_win.grab_set()
    load_revenue_data()

    filter_frame = tk.LabelFrame(rev_win, text="🔎 Lọc theo ngày", font=("Arial", 11, "bold"), bg="#f8f9fa", padx=15, pady=10)
    filter_frame.pack(fill="x", padx=15, pady=8)

    tk.Label(filter_frame, text="Từ ngày:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5)
    from_selector = DateSelector(filter_frame)
    from_selector.grid(row=0, column=1, padx=5)
    from_selector.set_date(date.today() - timedelta(days=30))

    tk.Label(filter_frame, text="Đến ngày:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=0, column=2, sticky="w", padx=5)
    to_selector = DateSelector(filter_frame)
    to_selector.grid(row=0, column=3, padx=5)
    to_selector.set_date(date.today())

    tk.Button(filter_frame, text="🔎 Lọc", command=lambda: refresh_revenue_tree(tree_r, lbl_total, from_selector.get_date(), to_selector.get_date()),
              bg="#3498db", fg="white", width=12).grid(row=0, column=4, padx=8)
    tk.Button(filter_frame, text="Hiển thị tất cả", command=lambda: refresh_revenue_tree(tree_r, lbl_total),
              bg="#95a5a6", fg="white", width=15).grid(row=0, column=5, padx=5)

    form = tk.LabelFrame(rev_win, text=" Nhập Doanh Thu ", font=("Arial", 11, "bold"), bg="#f8f9fa", padx=15, pady=12)
    form.pack(fill="x", padx=15, pady=8)

    tk.Label(form, text="Ngày:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
    e_ngay = DateSelector(form)
    e_ngay.grid(row=0, column=1, padx=10, pady=6)

    tk.Label(form, text="Số tiền doanh thu:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", pady=6)
    e_tien = tk.Entry(form, width=30, font=("Arial", 10))
    e_tien.grid(row=1, column=1, padx=10, pady=6)

    tk.Label(form, text="Ghi chú:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", pady=6)
    e_ghichu = tk.Entry(form, width=60, font=("Arial", 10))
    e_ghichu.grid(row=2, column=1, padx=10, pady=6)

    btn_f = tk.Frame(form, bg="#f8f9fa")
    btn_f.grid(row=3, column=0, columnspan=2, pady=12)
    tk.Button(btn_f, text="➕ Thêm", command=lambda: them_moi_doanhthu(e_ngay, e_tien, e_ghichu, tree_r, lbl_total), bg="#28a745", fg="white", width=12).pack(side="left", padx=5)
    tk.Button(btn_f, text="✏️ Sửa", command=lambda: sua_doanhthu(tree_r, e_ngay, e_tien, e_ghichu, lbl_total), bg="#ffc107", fg="black", width=12).pack(side="left", padx=5)
    tk.Button(btn_f, text="🗑️ Xóa", command=lambda: xoa_doanhthu(tree_r, lbl_total), bg="#e74c3c", fg="white", width=12).pack(side="left", padx=5)
    tk.Button(btn_f, text="📤 Export Excel", command=export_doanhthu, bg="#6f42c1", fg="white", width=15).pack(side="left", padx=5)

    tree_frame = tk.LabelFrame(rev_win, text=" Danh sách doanh thu ", font=("Arial", 11, "bold"), bg="#f8f9fa", padx=10, pady=8)
    tree_frame.pack(fill="both", expand=True, padx=15, pady=5)

    columns = ("STT", "Ngày", "Doanh thu", "Ghi chú")
    tree_r = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
    for col in columns:
        tree_r.heading(col, text=col)
        w = 120 if col == "Ghi chú" else 100
        tree_r.column(col, width=w, anchor="center")

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree_r.yview)
    tree_r.configure(yscrollcommand=vsb.set)
    tree_r.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    lbl_total = tk.Label(rev_win, text="💰 TỔNG DOANH THU: 0 VNĐ", font=("Arial", 14, "bold"), fg="#2e7d32", bg="#f8f9fa")
    lbl_total.pack(pady=15)

    refresh_revenue_tree(tree_r, lbl_total)

def them_moi_doanhthu(e_ngay, e_tien, e_ghichu, tree, lbl):
    ngay = e_ngay.get_date_str()
    tien = parse_money(e_tien.get())
    ghichu = e_ghichu.get().strip()
    if tien <= 0:
        messagebox.showwarning("Lỗi", "Số tiền phải lớn hơn 0!")
        return
    revenue_list.append({"ngay": ngay, "doanh_thu": tien, "ghi_chu": ghichu})
    save_revenue_data()
    refresh_revenue_tree(tree, lbl)
    e_tien.delete(0, tk.END)
    e_ghichu.delete(0, tk.END)
    messagebox.showinfo("Thành công", "Đã thêm doanh thu!")

def sua_doanhthu(tree, e_ngay, e_tien, e_ghichu, lbl):
    sel = tree.selection()
    if not sel:
        messagebox.showwarning("Chưa chọn", "Double-click vào dòng cần sửa!")
        return
    idx = int(tree.item(sel[0])['values'][0]) - 1
    tien = parse_money(e_tien.get())
    if tien <= 0:
        messagebox.showwarning("Lỗi", "Số tiền phải lớn hơn 0!")
        return
    revenue_list[idx]["ngay"] = e_ngay.get_date_str()
    revenue_list[idx]["doanh_thu"] = tien
    revenue_list[idx]["ghi_chu"] = e_ghichu.get().strip()
    save_revenue_data()
    refresh_revenue_tree(tree, lbl)
    messagebox.showinfo("Thành công", "Đã cập nhật!")

def xoa_doanhthu(tree, lbl):
    sel = tree.selection()
    if not sel: return
    if messagebox.askyesno("Xác nhận", "Xóa dòng này?"):
        idx = int(tree.item(sel[0])['values'][0]) - 1
        del revenue_list[idx]
        save_revenue_data()
        refresh_revenue_tree(tree, lbl)

def export_doanhthu():
    if not revenue_list:
        messagebox.showwarning("Không có dữ liệu", "Chưa có doanh thu nào!")
        return
    filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
    if filename:
        df = pd.DataFrame(revenue_list)
        df.to_excel(filename, index=False)
        messagebox.showinfo("Thành công", f"Đã export:\n{filename}")

def load_debt_data():
    global debt_list
    if DEBT_FILE.exists():
        try:
            with open(DEBT_FILE, 'r', encoding='utf-8') as f:
                debt_list = json.load(f)
        except:
            debt_list = []
    else:
        debt_list = []

def save_debt_data():
    try:
        with open(DEBT_FILE, 'w', encoding='utf-8') as f:
            json.dump(debt_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Lỗi", f"Lỗi lưu công nợ: {str(e)}")

def refresh_debt_tree(tree, total_label):
    for item in tree.get_children():
        tree.delete(item)
    for i, debt in enumerate(debt_list, 1):
        con_no = debt["so_tien_no"] - debt.get("da_thanh_toan", 0)
        days_debt = get_days_debt(debt.get("ngay_no", ""))
        tag = "overdue" if con_no > 0 and days_debt > 10 else "normal"
        tree.insert("", "end", values=(
            i, debt.get("khach_hang", ""), debt.get("zalo", ""),
            format_money(debt["so_tien_no"]),
            format_money(debt.get("da_thanh_toan", 0)),
            format_money(con_no),
            debt.get("ngay_no", ""),
            f"{days_debt} ngày",
            debt.get("ghi_chu", "")[:30]
        ), tags=(tag,))
    total = sum(d["so_tien_no"] - d.get("da_thanh_toan", 0) for d in debt_list)
    total_label.config(text=f"💰 TỔNG CÔNG NỢ: {format_money(total)}")
    tree.tag_configure("overdue", foreground="#d32f2f", font=("Arial", 10, "bold"))
    tree.tag_configure("normal", foreground="black")

def open_debt_window():
    debt_win = tk.Toplevel(root)
    debt_win.title("📋 Quản Lý Công Nợ Khách Hàng")
    debt_win.geometry("1150x680")
    debt_win.configure(bg="#f8f9fa")
    debt_win.grab_set()
    load_debt_data()

    form_frame = tk.LabelFrame(debt_win, text=" Nhập / Sửa Công Nợ ", font=("Arial", 11, "bold"), bg="#f8f9fa", padx=15, pady=12)
    form_frame.pack(fill="x", padx=15, pady=10)

    tk.Label(form_frame, text="Khách hàng (ID/Tên):", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
    e_khach = tk.Entry(form_frame, width=45, font=("Arial", 10))
    e_khach.grid(row=0, column=1, padx=10, pady=6)

    tk.Label(form_frame, text="Zalo / SĐT:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", pady=6)
    e_zalo = tk.Entry(form_frame, width=45, font=("Arial", 10))
    e_zalo.grid(row=1, column=1, padx=10, pady=6)

    tk.Label(form_frame, text="Số tiền nợ:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", pady=6)
    e_tien = tk.Entry(form_frame, width=45, font=("Arial", 10))
    e_tien.grid(row=2, column=1, padx=10, pady=6)

    tk.Label(form_frame, text="Ngày nợ:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="w", pady=6)
    e_ngay = DateSelector(form_frame)
    e_ngay.grid(row=3, column=1, padx=10, pady=6, sticky="w")

    tk.Label(form_frame, text="Ghi chú:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=4, column=0, sticky="w", pady=6)
    e_ghichu = tk.Entry(form_frame, width=60, font=("Arial", 10))
    e_ghichu.grid(row=4, column=1, padx=10, pady=6)

    btn_f = tk.Frame(form_frame, bg="#f8f9fa")
    btn_f.grid(row=5, column=0, columnspan=2, pady=12)
    tk.Button(btn_f, text="➕ Thêm Mới", command=lambda: them_moi_congno_debt(e_khach, e_zalo, e_tien, e_ngay, e_ghichu, tree_d, lbl_t), bg="#28a745", fg="white", font=("Arial", 10, "bold"), width=14).pack(side="left", padx=5)
    tk.Button(btn_f, text="✏️ Sửa", command=lambda: sua_congno_debt(tree_d, e_khach, e_zalo, e_tien, e_ngay, e_ghichu, lbl_t), bg="#ffc107", fg="black", font=("Arial", 10, "bold"), width=12).pack(side="left", padx=5)
    tk.Button(btn_f, text="🗑️ Xóa", command=lambda: xoa_congno_debt(tree_d, lbl_t), bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), width=12).pack(side="left", padx=5)
    tk.Button(btn_f, text="💰 Thanh Toán", command=lambda: thanh_toan_congno_debt(tree_d, lbl_t), bg="#17a2b8", fg="white", font=("Arial", 10, "bold"), width=15).pack(side="left", padx=5)
    tk.Button(btn_f, text="📤 Export Excel", command=export_congno_debt, bg="#6f42c1", fg="white", font=("Arial", 10, "bold"), width=15).pack(side="left", padx=5)

    tree_frame = tk.LabelFrame(debt_win, text=" Danh sách công nợ ", font=("Arial", 11, "bold"), bg="#f8f9fa", padx=10, pady=8)
    tree_frame.pack(fill="both", expand=True, padx=15, pady=5)

    columns = ("STT", "Khách hàng", "Zalo", "Nợ", "Đã trả", "Còn nợ", "Ngày", "Số ngày đã nợ", "Ghi chú")
    tree_d = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
    for col in columns:
        tree_d.heading(col, text=col)
        w = 140 if col in ["Khách hàng", "Ghi chú"] else 100
        tree_d.column(col, width=w, anchor="center")

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree_d.yview)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree_d.xview)
    tree_d.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree_d.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")

    def on_double_click(event):
        selected = tree_d.selection()
        if not selected: return
        idx = int(tree_d.item(selected[0])['values'][0]) - 1
        debt = debt_list[idx]
        e_khach.delete(0, tk.END); e_khach.insert(0, debt.get("khach_hang", ""))
        e_zalo.delete(0, tk.END);   e_zalo.insert(0, debt.get("zalo", ""))
        e_tien.delete(0, tk.END);   e_tien.insert(0, debt["so_tien_no"])
        if debt.get("ngay_no"):
            e_ngay.set_date(debt["ngay_no"])
        e_ghichu.delete(0, tk.END); e_ghichu.insert(0, debt.get("ghi_chu", ""))

    tree_d.bind("<Double-1>", on_double_click)

    lbl_t = tk.Label(debt_win, text="💰 TỔNG CÔNG NỢ: 0 VNĐ", font=("Arial", 14, "bold"), fg="#d32f2f", bg="#f8f9fa")
    lbl_t.pack(pady=18)

    refresh_debt_tree(tree_d, lbl_t)

def them_moi_congno_debt(e_khach, e_zalo, e_tien, e_ngay, e_ghichu, tree, lbl):
    khach = e_khach.get().strip()
    zalo = e_zalo.get().strip()
    tien = parse_money(e_tien.get())
    ngay = e_ngay.get_date_str()
    ghichu = e_ghichu.get().strip()
    if not khach or tien <= 0:
        messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập đầy đủ và số tiền hợp lệ!")
        return
    debt = {"id": str(uuid.uuid4())[:8].upper(), "khach_hang": khach, "zalo": zalo,
            "so_tien_no": tien, "da_thanh_toan": 0.0, "ngay_no": ngay,
            "ghi_chu": ghichu, "ngay_tao": datetime.now().strftime("%Y-%m-%d %H:%M")}
    debt_list.append(debt)
    save_debt_data()
    refresh_debt_tree(tree, lbl)
    e_tien.delete(0, tk.END)
    e_ghichu.delete(0, tk.END)
    messagebox.showinfo("Thành công", "Đã thêm khoản nợ mới!")

def sua_congno_debt(tree, e_khach, e_zalo, e_tien, e_ngay, e_ghichu, lbl):
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("Chưa chọn", "Vui lòng double-click vào dòng cần sửa!")
        return
    idx = int(tree.item(selected[0])['values'][0]) - 1
    if 0 <= idx < len(debt_list):
        tien = parse_money(e_tien.get())
        if tien <= 0:
            messagebox.showwarning("Lỗi", "Số tiền phải lớn hơn 0!")
            return
        debt_list[idx].update({
            "khach_hang": e_khach.get().strip(),
            "zalo": e_zalo.get().strip(),
            "so_tien_no": tien,
            "ngay_no": e_ngay.get_date_str(),
            "ghi_chu": e_ghichu.get().strip()
        })
        save_debt_data()
        refresh_debt_tree(tree, lbl)
        messagebox.showinfo("Thành công", "Đã cập nhật!")

def xoa_congno_debt(tree, lbl):
    selected = tree.selection()
    if not selected: return
    if messagebox.askyesno("Xác nhận", "Xóa khoản nợ này?"):
        idx = int(tree.item(selected[0])['values'][0]) - 1
        if 0 <= idx < len(debt_list):
            del debt_list[idx]
            save_debt_data()
            refresh_debt_tree(tree, lbl)

def thanh_toan_congno_debt(tree, lbl):
    selected = tree.selection()
    if not selected: return
    amount = simpledialog.askfloat("Thanh toán", "Nhập số tiền thanh toán:", minvalue=0)
    if amount is None or amount <= 0: return
    idx = int(tree.item(selected[0])['values'][0]) - 1
    if 0 <= idx < len(debt_list):
        debt_list[idx]["da_thanh_toan"] = min(debt_list[idx].get("da_thanh_toan", 0) + amount, debt_list[idx]["so_tien_no"])
        save_debt_data()
        refresh_debt_tree(tree, lbl)

def export_congno_debt():
    if not debt_list:
        messagebox.showwarning("Không có dữ liệu", "Chưa có công nợ nào!")
        return
    filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
    if filename:
        df = pd.DataFrame(debt_list)
        df['con_no'] = df['so_tien_no'] - df.get('da_thanh_toan', 0)
        df.to_excel(filename, index=False)
        messagebox.showinfo("Thành công", f"Đã export:\n{filename}")

# ==================== TÍNH TOÁN (ĐÃ CẢI TIẾN) ====================
def calculate():
    global last_profit
    output = ""
    nums_group = [int(num) for num in re.findall(r'\d+', entry_group.get().strip())]
    total_group = sum(nums_group) if nums_group else 0
    current_tab = notebook.tab(notebook.select(), "text")

    if current_tab == "Ghép Nhóm":
        try:
            low, high = map(int, re.findall(r'\d+', entry_range.get().strip()))
            target = int(entry_num_groups.get().strip() or 0)
            if target == 0:                  # ← NHẬP 0 = TỐI ĐA
                target = 9999
        except:
            messagebox.showerror("Lỗi", "Vui lòng nhập đúng khoảng nhóm!")
            return

        groups = []
        remaining = nums_group[:]
        created = 0
        while created < target and remaining:
            subset, is_complete = find_best_group(remaining, low, high)
            if not subset: break
            s = sum(subset)
            groups.append((subset, s, is_complete))
            for val in subset: remaining.remove(val)
            created += 1

        target_str = "tối đa" if target == 9999 else str(target)
        output += f"📊 TỔNG DÃY: {total_group:,}\n"
        output += f"🎯 Mong ghép {target_str} nhóm → Đã ghép {len(groups)} nhóm\n\n"
        output += "✅ KẾT QUẢ GHÉP NHÓM:\n\n"
        temp_map = {k: v[:] for k, v in item_map.items()}
        for i, (g, s, complete) in enumerate(groups, 1):
            output += f"Nhóm {i} (Tổng = {s}):\n"
            for num in sorted(g, reverse=True):
                if num in temp_map and temp_map[num]:
                    name, send_id = temp_map[num].pop(0)
                    output += f"   • {num:>6} → {name:<30} | ID gửi: {send_id}\n"
                    output += "--------------------------------------------------------------------------\n"
                else:
                    output += f"   • {num:>6} → ??? Không tìm thấy tên\n"
            output += f"   {'✅ HOÀN CHỈNH' if complete else f'⚠️ Còn thiếu {low - s}'}\n"
            output += "══════════════════════════════════════════════════════════════════════════════\n\n"

        if remaining:
            remaining_sorted = sorted(remaining, reverse=True)   # ← SẮP XẾP GIẢM DẦN
            output += f"🔸 SỐ CÒN LẠI ({len(remaining)} số): {remaining_sorted}\n"

            # Gợi ý còn thiếu để tạo nhóm mới
            if remaining_sorted:
                max_possible = sum(remaining_sorted)
                if max_possible >= low:
                    output += f"🔹 Gợi ý: Có thể tạo thêm 1 nhóm (tổng còn lại đủ {low} ~ {high})\n"
                else:
                    deficit = low - max_possible
                    output += f"🔹 Gợi ý: Cần thêm ít nhất {deficit} số nữa để tạo nhóm mới (tổng còn thiếu {deficit})\n"

    elif current_tab == "Tính % Sale":
        text_sale = entry_sale.get().strip()
        percent_str = entry_percent.get().strip().replace('%', '').strip()
        nums_sale = [int(num) for num in re.findall(r'\d+', text_sale)] if text_sale else nums_group
        total_sale = sum(nums_sale)
        percent = float(percent_str) if percent_str else 0.0
        discount = total_sale * (percent / 100)
        payable = total_sale - discount
        output += f"💰 ÁP DỤNG {percent}% SALE\n"
        output += f"   Tổng gốc      : {total_sale:>15,.2f}\n"
        output += f"   Giảm giá      : {discount:>15,.2f}\n"
        output += f"   TIỀN CẦN TRẢ : {payable:>15,.2f}   ←←←\n"

    elif current_tab == "Lợi Nhuận Sale Game":
        try:
            gia_su_kien = float(entry_gia_su_kien.get())
            phan_tram_ingame = float(entry_phan_tram_ingame.get())
            gia_nhan = float(entry_gia_nhan.get())
            so_acc = int(entry_so_acc.get())
            gia_nap = round(gia_su_kien * 0.95, 1)
            gia_sale = round(gia_su_kien * (1 - phan_tram_ingame / 100), 1)
            lai = round(gia_sale + gia_nhan - gia_nap, 1)
            tong_lai = round(lai * so_acc, 1)
            last_profit = tong_lai
            output += f"💎 TÍNH LỢI NHUẬN SALE GAME\n"
            output += f"   GIÁ SỰ KIỆN       : {gia_su_kien:>15,.2f}\n"
            output += f"   GIÁ NẠP VC        : {gia_nap:>15,.2f}\n"
            output += f"   GIÁ SALE          : {gia_sale:>15,.2f}\n"
            output += f"   GIÁ NHẬN          : {gia_nhan:>15,.2f}\n"
            output += f"   LÃI (1 acc)       : {lai:>15,.2f}\n"
            output += f"   SỐ ACC NHẬN      : {so_acc:>15}\n"
            output += f"   TỔNG LỢI NHUẬN    : {tong_lai:>15,.2f}   ←←←\n"
        except:
            output += "⚠️ Vui lòng nhập đầy đủ thông tin Lợi Nhuận!"

    text_output.delete(1.0, tk.END)
    text_output.insert(tk.END, output)

def find_best_group(remaining, low, high):
    if not remaining: return None, None
    nums = sorted([x for x in remaining if x > 0], reverse=True)
    if not nums: return None, None
    subset = []
    current_sum = 0
    for num in nums:
        if current_sum + num <= high:
            subset.append(num)
            current_sum += num
        if current_sum >= low: break
    is_complete = low <= current_sum <= high
    return subset, is_complete

def clear_all_data():
    entry_group.delete(0, tk.END)
    entry_range.delete(0, tk.END)
    entry_num_groups.delete(0, tk.END)
    entry_num_groups.insert(0, "0")
    entry_sale.delete(0, tk.END)
    entry_percent.delete(0, tk.END)
    entry_gia_su_kien.delete(0, tk.END)
    entry_phan_tram_ingame.delete(0, tk.END)
    entry_gia_nhan.delete(0, tk.END)
    entry_so_acc.delete(0, tk.END)
    text_output.delete(1.0, tk.END)
    messagebox.showinfo("🗑️ Đã xóa", "Đã xóa sạch toàn bộ dữ liệu!")

# ==================== IMPORT & EXPORT ====================
def import_item_map():
    global item_map
    file_path = filedialog.askopenfilename(title="Import Bảng Giá Món Hàng (Excel)", filetypes=[("Excel files", "*.xlsx *.xls")])
    if not file_path: return
    try:
        df = pd.read_excel(file_path, header=None)
        item_map.clear()
        count = 0
        for _, row in df.iterrows():
            if len(row) >= 3:
                try:
                    num = int(float(row[0]))
                    name = str(row[1]).strip()
                    send_id = str(row[2]).strip()
                    item_map[num].append((name, send_id))
                    count += 1
                except: continue
        messagebox.showinfo("✅ Thành công", f"Đã import {count} món hàng!")
    except Exception as e:
        messagebox.showerror("Lỗi import", str(e))

def import_file_to_entry(entry_widget):
    file_path = filedialog.askopenfilename(title="Chọn file Dãy số ghép nhóm", filetypes=[("Excel files", "*.xlsx *.xls"), ("Text files", "*.txt")])
    if not file_path: return
    try:
        path = Path(file_path)
        if path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, header=None)
            numbers = [int(float(x)) for x in df.iloc[:, 0].dropna() if str(x).strip()]
        else:
            content = path.read_text(encoding='utf-8')
            numbers = [int(num) for num in re.findall(r'\d+', content)]
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, ' '.join(map(str, numbers)))
        messagebox.showinfo("Thành công", f"✅ Đã import {len(numbers)} số!")
    except Exception as e:
        messagebox.showerror("Lỗi import", str(e))

def show_import_menu():
    menu_win = tk.Toplevel(root)
    menu_win.title("📂 Chọn loại import")
    menu_win.geometry("420x220")
    menu_win.configure(bg="#2c3e50")
    menu_win.grab_set()
    menu_win.resizable(False, False)
    tk.Label(menu_win, text="📂 Chọn dữ liệu cần import", font=("Arial", 14, "bold"), fg="white", bg="#2c3e50").pack(pady=20)
    tk.Button(menu_win, text="📋 Import Dãy Số Ghép Nhóm", command=lambda: [import_file_to_entry(entry_group), menu_win.destroy()], bg="#3498db", fg="white", font=("Arial", 11, "bold"), width=35, height=2).pack(pady=8)
    tk.Button(menu_win, text="📋 Import Bảng Giá Món Hàng", command=lambda: [import_item_map(), menu_win.destroy()], bg="#e67e22", fg="white", font=("Arial", 11, "bold"), width=35, height=2).pack(pady=8)
    tk.Button(menu_win, text="❌ Hủy", command=menu_win.destroy, bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), width=20).pack(pady=12)

def export_to_excel():
    global last_exported_file
    result_text = text_output.get("1.0", tk.END).strip()
    if not result_text:
        messagebox.showwarning("Chưa có kết quả", "Vui lòng bấm TÍNH TOÁN trước!")
        return
    filename = entry_filename.get().strip() or "ket_qua.xlsx"
    if not filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        filename += '.xlsx'
    try:
        lines = [line.strip() for line in result_text.split('\n') if line.strip()]
        pd.DataFrame({'Kết quả': lines}).to_excel(filename, index=False, engine='openpyxl')
        last_exported_file = filename
        messagebox.showinfo("✅ Thành công", f"Đã xuất file:\n{filename}")
        btn_open.config(state='normal')
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))

def open_exported_file():
    global last_exported_file
    if last_exported_file and os.path.exists(last_exported_file):
        os.startfile(last_exported_file)
    else:
        messagebox.showwarning("Chưa có file", "Vui lòng xuất file trước!")

# ==================== GIAO DIỆN CHÍNH ====================
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("950x780")
    root.configure(bg="#f8f9fa")
    root.resizable(False, False)
    root.withdraw()

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=15, pady=10)

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure("TNotebook.Tab", font=("Arial", 12, "bold"), padding=[25, 12])
    style.map("TNotebook.Tab", background=[("selected", "#4CAF50")], foreground=[("selected", "white")])

    # Tab Ghép Nhóm
    tab_group = tk.Frame(notebook, bg="#f8f9fa")
    notebook.add(tab_group, text="Ghép Nhóm")
    tk.Label(tab_group, text="Dãy số ghép nhóm:", bg="#f8f9fa", font=("Arial", 11, "bold")).pack(anchor="w", padx=20, pady=(15,5))
    frame_group = tk.Frame(tab_group, bg="#f8f9fa")
    frame_group.pack(fill="x", padx=20)
    entry_group = tk.Entry(frame_group, width=70, font=("Arial", 10))
    entry_group.pack(side="left", expand=True, fill="x", padx=(0,8))
    tk.Button(frame_group, text="📂 Import Dữ Liệu", command=show_import_menu, bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=16).pack(side="left")

    tk.Label(tab_group, text="Khoảng nhóm (ví dụ: 330~336):", bg="#f8f9fa", font=("Arial", 11, "bold")).pack(anchor="w", padx=20, pady=(15,5))
    entry_range = tk.Entry(tab_group, width=30, font=("Arial", 10))
    entry_range.pack(anchor="w", padx=20)

    tk.Label(tab_group, text="Số acc / nhóm muốn ghép (0 = tối đa):", bg="#f8f9fa", font=("Arial", 11, "bold")).pack(anchor="w", padx=20, pady=(15,5))
    entry_num_groups = tk.Entry(tab_group, width=15, font=("Arial", 10))
    entry_num_groups.pack(anchor="w", padx=20)
    entry_num_groups.insert(0, "0")

    # Tab Tính % Sale
    tab_sale = tk.Frame(notebook, bg="#f8f9fa")
    notebook.add(tab_sale, text="Tính % Sale")
    tk.Label(tab_sale, text="Dãy số tính Sale (nếu khác):", bg="#f8f9fa", font=("Arial", 10)).pack(anchor="w", padx=20, pady=(15,5))
    frame_sale = tk.Frame(tab_sale, bg="#f8f9fa")
    frame_sale.pack(fill="x", padx=20)
    entry_sale = tk.Entry(frame_sale, width=70, font=("Arial", 10))
    entry_sale.pack(side="left", expand=True, fill="x", padx=(0,8))
    tk.Button(frame_sale, text="📂 Import", command=lambda: import_file_to_entry(entry_sale), bg="#1976D2", fg="white", font=("Arial", 9, "bold")).pack(side="left")
    tk.Label(tab_sale, text="% Sale (ví dụ: 10):", bg="#f8f9fa", font=("Arial", 11, "bold")).pack(anchor="w", padx=20, pady=(15,5))
    entry_percent = tk.Entry(tab_sale, width=15, font=("Arial", 10))
    entry_percent.pack(anchor="w", padx=20)

    # Tab Lợi Nhuận Sale Game
    tab_profit = tk.Frame(notebook, bg="#f8f9fa")
    notebook.add(tab_profit, text="Lợi Nhuận Sale Game")
    frame_profit = tk.Frame(tab_profit, bg="#f8f9fa")
    frame_profit.pack(fill="x", padx=20, pady=20)
    tk.Label(frame_profit, text="GIÁ SỰ KIỆN:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=8)
    entry_gia_su_kien = tk.Entry(frame_profit, width=25, font=("Arial", 10))
    entry_gia_su_kien.grid(row=0, column=1, padx=10, pady=8)
    tk.Label(frame_profit, text="% INGAME:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", pady=8)
    entry_phan_tram_ingame = tk.Entry(frame_profit, width=25, font=("Arial", 10))
    entry_phan_tram_ingame.grid(row=1, column=1, padx=10, pady=8)
    tk.Label(frame_profit, text="GIÁ NHẬN SỰ KIỆN:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", pady=8)
    entry_gia_nhan = tk.Entry(frame_profit, width=25, font=("Arial", 10))
    entry_gia_nhan.grid(row=2, column=1, padx=10, pady=8)
    tk.Label(frame_profit, text="SỐ ACC NHẬN:", bg="#f8f9fa", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="w", pady=8)
    entry_so_acc = tk.Entry(frame_profit, width=25, font=("Arial", 10))
    entry_so_acc.grid(row=3, column=1, padx=10, pady=8)

    # Nút chính
    btn_frame_main = tk.Frame(root, bg="#f8f9fa")
    btn_frame_main.pack(pady=12)
    tk.Button(btn_frame_main, text="🚀 TÍNH TOÁN", command=calculate, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), height=2, width=12).pack(side="left", padx=4)
    tk.Button(btn_frame_main, text="🗑️ XÓA", command=clear_all_data, bg="#e74c3c", fg="white", font=("Arial", 11, "bold"), height=2, width=10).pack(side="left", padx=4)
    tk.Button(btn_frame_main, text="📋 Công Nợ", command=open_debt_window, bg="#6f42c1", fg="white", font=("Arial", 11, "bold"), height=2, width=12).pack(side="left", padx=4)
    tk.Button(btn_frame_main, text="📊 Doanh Thu", command=open_revenue_window, bg="#2196F3", fg="white", font=("Arial", 11, "bold"), height=2, width=13).pack(side="left", padx=4)
    tk.Button(btn_frame_main, text="🧮 Máy Tính", command=open_calculator, bg="#9C27B0", fg="white", font=("Arial", 11, "bold"), height=2, width=11).pack(side="left", padx=4)
    tk.Button(btn_frame_main, text="🌐 Mua Key", command=lambda: webbrowser.open(PRICING_URL), bg="#f39c12", fg="white", font=("Arial", 11, "bold"), height=2, width=11).pack(side="left", padx=4)

    # Export + Ghi Doanh Thu
    export_frame = tk.Frame(root, bg="#f8f9fa")
    export_frame.pack(fill="x", padx=20, pady=8)
    tk.Label(export_frame, text="Tên file xuất:", bg="#f8f9fa", font=("Arial", 10, "bold")).pack(anchor="w")
    entry_filename = tk.Entry(export_frame, width=60, font=("Arial", 10))
    entry_filename.pack(fill="x", pady=4)
    entry_filename.insert(0, "ket_qua.xlsx")

    btn_frame = tk.Frame(export_frame, bg="#f8f9fa")
    btn_frame.pack(fill="x", pady=8)
    tk.Button(btn_frame, text="📤 Xuất Excel", command=export_to_excel, bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=15).pack(side="left", padx=5)
    btn_open = tk.Button(btn_frame, text="📂 Mở File Excel", command=open_exported_file, bg="#6A1B9A", fg="white", font=("Arial", 10, "bold"), width=18, state='disabled')
    btn_open.pack(side="left", padx=5)
    tk.Button(btn_frame, text="💰 Ghi Doanh Thu", command=record_profit_to_revenue, bg="#00b894", fg="white", font=("Arial", 10, "bold"), width=18).pack(side="left", padx=5)

    tk.Label(root, text="Kết quả:", bg="#f8f9fa", font=("Arial", 11, "bold")).pack(anchor="w", padx=20, pady=(5,0))
    text_output = scrolledtext.ScrolledText(root, height=19, font=("Consolas", 10), bg="#ffffff")
    text_output.pack(padx=20, pady=8, fill="both", expand=True)

    # ==================== KHỞI ĐỘNG ====================
valid, remaining_days, status_text = load_license_info()
update_title(valid, status_text)

if valid:
        root.deiconify()           # Hiện cửa sổ chính
        check_overdue_reminder()
        root.mainloop()
else:
        if LICENSE_FILE.exists() and remaining_days <= 0:
            messagebox.showerror("❌ HẾT HẠN", "License key của bạn đã hết hạn!\nVui lòng nhập key mới.")
        show_license_dialog()