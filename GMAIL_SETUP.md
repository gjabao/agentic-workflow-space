# 📧 Gmail Setup cho Email Reports

## Bước 1: Bật 2-Step Verification

1. Vào [Google Account Security](https://myaccount.google.com/security)
2. Tìm "2-Step Verification"
3. Click "Get Started" và follow hướng dẫn
4. Xác nhận bằng phone number

## Bước 2: Tạo App Password

1. Sau khi bật 2-Step Verification, quay lại [Security page](https://myaccount.google.com/security)
2. Tìm "App passwords" (ở phần "2-Step Verification")
3. Click vào "App passwords"
4. Select app: **Mail**
5. Select device: **Mac** (hoặc device bạn đang dùng)
6. Click **Generate**
7. Copy 16-character password (ví dụ: `abcd efgh ijkl mnop`)

## Bước 3: Cập nhật .env

1. Mở file `.env`
2. Thay thế `YOUR_GMAIL_APP_PASSWORD_HERE` bằng password vừa copy
3. **Lưu ý:** Paste password KHÔNG có spaces (remove spaces)

```bash
# Sai ❌
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop

# Đúng ✅
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

## Bước 4: Test Email

Chạy command này để test:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
python3 execution/email_campaign_report.py
```

Bạn sẽ nhận được email báo cáo trong vài giây!

## Troubleshooting

### Lỗi "Username and Password not accepted"
- Đảm bảo đã bật 2-Step Verification
- Kiểm tra App Password không có spaces
- Thử generate lại App Password

### Lỗi "SMTPAuthenticationError"
- Kiểm tra GMAIL_USER đúng email
- Kiểm tra GMAIL_APP_PASSWORD copy đúng

### Không nhận được email
- Check spam folder
- Verify email address trong .env
- Check Gmail quota (có thể gửi 500 emails/day)

## Security Notes

⚠️ **QUAN TRỌNG:**
- KHÔNG share App Password với ai
- KHÔNG commit .env lên GitHub (đã có trong .gitignore)
- Nếu lộ password, revoke và tạo mới

---

**Need help?** Check [Google App Passwords Support](https://support.google.com/accounts/answer/185833)
