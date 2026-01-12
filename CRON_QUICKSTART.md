# 🚀 Cron Jobs Quick Start - 5 Phút Setup

## ✅ Những Gì Bạn Sẽ Nhận Được

Sau khi setup, bạn sẽ nhận được:

📧 **Email report mỗi sáng 7 AM** (Hanoi time) về tất cả campaigns đang active
🔍 **Tự động monitor** mỗi giờ để phát hiện vấn đề sớm
🚨 **Cảnh báo** nếu bounce rate cao, reply rate thấp, hoặc có vấn đề deliverability
🎉 **Phát hiện winners** - campaigns có reply rate >3% để scale

---

## 📋 Checklist Trước Khi Bắt Đầu

- [ ] Python 3 đã cài đặt
- [ ] File `.env` có `INSTANTLY_API_KEY`
- [ ] Gmail account (giabaongb0305@gmail.com)
- [ ] 10 phút thời gian

---

## 🎯 Setup trong 3 Bước

### **Bước 1: Setup Gmail App Password** (3 phút)

1. Vào https://myaccount.google.com/security
2. Bật **2-Step Verification** (nếu chưa có)
3. Tìm **App passwords** → Select **Mail** → Select **Mac**
4. Copy 16-character password (ví dụ: `abcdefghijklmnop`)
5. Mở file `.env` và thêm:

```bash
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

📖 **Chi tiết:** Xem [GMAIL_SETUP.md](GMAIL_SETUP.md)

---

### **Bước 2: Test Email Report** (1 phút)

Chạy command này để test gửi email:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
python3 execution/email_campaign_report.py
```

**Kết quả mong đợi:**
```
🔍 Fetching active campaigns...
✓ Found 1 active campaigns

📧 Connecting to Gmail SMTP...
📨 Sending email to giabaongb0305@gmail.com...
✅ Email sent successfully!
✓ Copy saved to: .tmp/email_reports/report_...html
```

👉 **Check email inbox** - Bạn sẽ nhận được báo cáo đẹp!

---

### **Bước 3: Install Cron Jobs** (1 phút)

Chạy setup script:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
bash setup_cron.sh
```

**Nhấn `y` khi được hỏi:**
```
Install these cron jobs? [y/N]: y
```

**Kết quả:**
```
✓✓✓ Cron jobs installed successfully!

Schedule:
  📧 Email Report:    Every day at 7 AM Hanoi time → giabaongb0305@gmail.com
  🔍 Hourly Check:    Every hour (9 AM - 7 PM Hanoi time)
  🗑️  Log Cleanup:     Every Sunday at midnight
```

---

## ✅ XOng! Cron Jobs Đã Active

Giờ bạn có thể:
- **Ngủ yên** - Hệ thống tự động monitor 24/7
- **Nhận email** mỗi sáng 7 AM với campaign performance
- **Phát hiện sớm** nếu có vấn đề deliverability hoặc low performance

---

## 📊 Bạn Sẽ Nhận Được Gì Trong Email?

### Email Report Mẫu:

```
📊 Instantly Campaign Performance Report
December 23, 2025 at 7:00 AM

┌─────────────┬──────────┬──────────┬──────────┐
│  🚨 Critical│ ⚠️ Warning│ 🎉 Winners│ ✅ Healthy│
│      0      │     0     │     1     │     0     │
└─────────────┴──────────┴──────────┴──────────┘

Campaign: Execuxe-Search-UAE
Status: Active
Health: 🎉 Excellent
Leads: 372 | Sent: 1,078
Reply Rate: 2.15% ✅ | Bounce: 0.74% ✅
Opportunities: 7

🎉 Excellent reply rate: 2.15%!
→ Scale this campaign - add more leads or increase daily limit
```

### Alerts Bạn Sẽ Nhận:

**🚨 Critical:**
- Bounce rate >5% → STOP campaign ngay
- 0 replies sau 200 emails → Rewrite copy

**⚠️ Warning:**
- Reply rate <1% sau 100 emails → Cần cải thiện
- Bounce rate >2% → Monitor closely

**🎉 Winners:**
- Reply rate >3% → Scale ngay!

---

## 🔍 Kiểm Tra Cron Jobs Đang Chạy

```bash
# View cron jobs
crontab -l

# View logs real-time
tail -f .tmp/cron_logs/email_report.log

# View email reports đã gửi
ls -la .tmp/email_reports/
```

---

## 🛠️ Troubleshooting

### Email không gửi được

**Check 1:** Verify Gmail App Password
```bash
grep GMAIL_APP_PASSWORD .env
```

**Check 2:** Test manual
```bash
python3 execution/email_campaign_report.py
```

**Check 3:** View error logs
```bash
cat .tmp/cron_logs/email_report.log
```

### Cron job không chạy

**Check 1:** Verify cron jobs installed
```bash
crontab -l | grep "Instantly"
```

**Check 2:** Máy phải BẬT vào 7 AM
- Cron jobs chỉ chạy khi máy bật
- Nếu muốn chạy khi máy tắt → Dùng GitHub Actions (tôi có thể setup)

**Check 3:** Check system cron logs
```bash
# macOS
log show --predicate 'process == "cron"' --last 1h

# Linux
grep CRON /var/log/syslog
```

---

## 🎛️ Tùy Chỉnh Schedule

Muốn thay đổi thời gian? Edit cron jobs:

```bash
crontab -e
```

**Cron syntax:**
```
0 0 * * *  → Midnight (7 AM Hanoi = 0 AM UTC)
0 */2 * * * → Mỗi 2 giờ
30 8 * * 1-5 → 8:30 AM thứ 2-6
```

**Hoặc chạy lại setup:**
```bash
bash setup_cron.sh  # Sẽ replace old jobs
```

---

## 🔄 Uninstall Cron Jobs

Nếu muốn tắt:

```bash
# Remove tất cả cron jobs
crontab -r

# Hoặc edit và xóa dòng Instantly
crontab -e
```

---

## 📚 Next Steps

Sau khi cron jobs chạy tốt, bạn có thể:

1. **Add more workflows:**
   - A/B test automation
   - Reply categorization
   - Lead upload automation

2. **Upgrade to GitHub Actions:**
   - Chạy trên cloud (máy tắt vẫn chạy)
   - Tôi đã setup sẵn `.github/workflows/daily-monitor.yml`

3. **Setup webhooks:**
   - Real-time alerts khi có reply
   - Instant notification

**Muốn setup cái nào? Cứ bảo tôi!** 🚀

---

## 📞 Support

**Có vấn đề?**
- Check [GMAIL_SETUP.md](GMAIL_SETUP.md) cho Gmail issues
- View logs trong `.tmp/cron_logs/`
- Test manual: `python3 execution/email_campaign_report.py`

**Questions?**
Cứ hỏi tôi! Tôi sẵn sàng giúp. 😊
