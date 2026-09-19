痛點: 不知道如何增進自己的職能（例如學生）。

提供現狀:
- 職業、產業，或特定公司的特定職位
- 履歷

系統會:
1. 從內建職缺資料（可加上你貼的 JD）統計被提到最多次的前 5 個 skill
2. 請 IFM 模型依履歷缺口排出 12 週學習規劃與資源
3. 前端以甘特圖、學習細項、技能長條圖呈現

啟動:

```
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe backend\app.py
```

瀏覽器打開 http://127.0.0.1:5000

API key 放在專案根目錄 `.env`（`IFM_API_KEY`）。若模型呼叫失敗，後端會用規則備援產生可展示的計畫。
