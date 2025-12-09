# ☁️ **Smart Cloud Optimizer**

---

## 🎯 **Main Idea**

The **Smart Cloud Optimizer** is a project that helps people and companies **save money on AWS Cloud** automatically.

Right now, most people use AWS but **don’t know which instance or service is best** for their needs.

Some choose big instances they don’t need (wasting money 💸), and others buy too small ones (causing performance issues).

This project solves that problem by combining **Machine Learning (ML)** and **Artificial Intelligence (AI)** together:

- **AI Recommendation System →** helps *new users* who have no AWS experience yet.
- **ML Optimization Engine →** helps *experienced users* who already have AWS data and want to optimize their usage.

Together, they create one **smart platform** that works for everyone.

---

## 🚨 **The Problem**

| User Type | Main Problem | Example |
| --- | --- | --- |
| 🧍 New AWS Users | Don’t know which instance or plan to choose. AWS has too many options. | A beginner wants to host a website but doesn’t know which EC2 type fits his budget. |
| 👨‍💻 Experienced AWS Users | Already using AWS but paying too much for resources they don’t need. | A small company runs servers 24/7 even though they only need them 8 hours/day. |

Both face the same issue → **Cloud spending is high because of wrong choices and no automation.**

---

## 💡 **The Solution**

Our solution combines **two systems** that work together inside one dashboard:

### 🧠 1. **AI Recommendation Module (for New Users)**

- Works when the user **doesn’t have AWS data** yet.
- Asks **simple questions** like:
    - What type of application are you building?
    - How many daily users do you expect?
    - How many hours per day will it run?
    - What’s your budget per month?
- The answers are combined into one **structured text (prompt)**.
- That text is sent to an **AI model** (like OpenAI or AWS Bedrock).
- The AI then gives:
    1. The best AWS setup (for example: t3.micro, On-Demand)
    2. Estimated monthly cost (like $4.10)
    3. Explanation (why this choice is best)

✅ So even beginners can start with confidence without wasting money.

---

### 📈 2. **Optimizer & Forecasting Engine (for Active Users)**

- Works when the user **already has AWS usage data**.
- Connects to AWS APIs (using `boto3` library):
    - **Cost Explorer API** → daily cost data
    - **CloudWatch API** → CPU, memory, network usage
    - **EC2 Describe API** → list of running instances
    - **Pricing API** → current prices of AWS instances
- The system:
    1. Analyzes historical cost and usage
    2. Predicts the next 30 days using **Prophet / SARIMAX models**
    3. Suggests the cheapest combination of On-Demand, Reserved, and Spot Instances using **optimization algorithms (PuLP / OR-Tools)**
    4. Detects cost spikes (anomalies) and provides insights.

✅ So advanced users can cut monthly bills by 15–30% without hurting performance.

---

## 🔁 **How Both Systems Work Together**

### Step-by-Step Process

1. **User opens the system**
    - Chooses whether they already have an AWS account or not.
2. **If user is new (no data):**
    - The AI module starts.
    - User answers 5–7 simple questions.
    - System builds a text summary (prompt).
    - AI returns a ready AWS setup recommendation.
3. **If user already has data:**
    - The system collects AWS metrics through APIs.
    - It runs the forecasting + optimization process.
    - Produces detailed reports with savings and future predictions.
4. **Unified Dashboard:**
    - Both results (AI & ML) are shown side by side.
    - The user can compare AI’s suggestion vs. real optimization.

---

## 🧩 **Visual Workflow**

![image.png](attachment:4952d8cd-10d8-4071-b36b-f13a29d27ff1:image.png)

---

## 📊 **Example Case**

### 👤 New User Example:

- User answers:
    - App type: Website
    - Users/day: 1000
    - Uptime: 12 hours
    - Importance: Medium
    - Budget: $10

→ System builds a prompt:

> “Recommend the best AWS setup for a medium website with 1000 daily users, 12-hour uptime, and $10/month budget.”
> 

**AI Output:**

- Recommended instance: t3.micro
- Estimated cost: $4.10/month
- Reason: “Good balance between performance and cost for medium traffic.”

---

### 👨‍💻 Active User Example:

- Current AWS cost = $30/month
- CPU average = 15%
- System forecast (next month) = $28 expected
- Optimizer suggests: **Switch to Reserved t3.micro → $3.00/month**

---

### 🔍 Final Dashboard

| Mode | Type | Estimated Cost | Saving |
| --- | --- | --- | --- |
| AI Recommendation | t3.micro (On-Demand) | $4.10 | — |
| ML Optimizer | t3.micro (Reserved 1 Year) | $3.00 | +25% |

✅ User sees both results and learns how to save more.

---

## ⚙️ **System Architecture Overview**

| Layer | Description | Tools / Frameworks |
| --- | --- | --- |
| **Frontend Dashboard** | User interface for input and output | Streamlit |
| **AI Module** | Collects user input and sends structured prompt to AI | OpenAI API / AWS Bedrock |
| **Data Collection Layer** | Fetches AWS data via SDK | boto3 |
| **Forecasting Engine** | Predicts next month’s usage | Prophet / SARIMAX |
| **Optimization Engine** | Finds cheapest instance combination | OR-Tools / PuLP |
| **Database Layer** | Stores responses and historical data | SQLite / CSV |
| **Deployment** | Hosts the system | Streamlit Cloud / Render / AWS Free Tier |

---

## 🧠 **Data Flow (Simplified)**

| Step | Input | Process | Output |
| --- | --- | --- | --- |
| 1 | User input | System creates structured prompt | Text summary |
| 2 | Prompt → AI | AI model generates recommendations | AWS setup & cost |
| 3 | AWS metrics | ML model predicts usage | Forecast graph |
| 4 | Optimizer | Runs cost-reduction logic | Best resource mix |
| 5 | Dashboard | Combines both results | Unified display |

---

## ✅ **Key Advantages**

| Feature | Benefit |
| --- | --- |
| **Covers all users** | Works for both beginners and professionals. |
| **AI = Smart Start** | Helps users with no AWS experience. |
| **ML = Deep Optimization** | Uses real data for accurate cost reduction. |
| **Forecasting** | Predicts future demand and cost trends. |
| **Unified Dashboard** | All insights in one clear interface. |
| **Educational Impact** | Helps students understand cloud cost analysis. |

---

## ⚠️ **Limitations & How We Handle Them**

| Limitation | Description | How We Fix It |
| --- | --- | --- |
| **AI might guess wrong** | If prompt is unclear. | Use structured format with clear fields. |
| **Costs may change daily** | AWS prices update often. | Sync Pricing API weekly. |
| **Data privacy** | Need to protect AWS credentials. | Use read-only IAM policy and never store keys. |
| **Limited free tier** | Some APIs have limits. | Use cached results for testing. |

---

## 🧾 **Summary**

> The Smart Cloud Optimizer is a modern cloud management platform that combines AI-based recommendations with Machine Learning optimization.
> 
> 
> It helps beginners choose the right AWS setup and assists advanced users in reducing cost and predicting usage.
> 
> Together, both systems make cloud management **smarter, cheaper, and easier for everyone.**
> 

---