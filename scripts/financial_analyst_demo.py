#!/usr/bin/env python3
"""
Financial Analyst Demo for TrustiPay Analytics

This script simulates a financial analyst managing 10 diverse customers.
For each customer, it:
1. Generates realistic transaction history based on their financial profile
2. Ingests transactions via the TrustiPay Analytics API
3. Displays comprehensive analysis including:
   - Transaction summary
   - Financial Health Score (FHS)
   - Behavior profile
   - Anomalies with xAI factors
   - Personalized recommendations
4. Demonstrates batch prediction capability

Customer Profiles:
- Conservative savers
- Balanced spenders
- High spenders
- Students
- Freelancers
- Business owners
- Various spending patterns and risk profiles
"""

import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import requests

# Configuration
API_BASE_URL = "http://127.0.0.1:8005"
INGEST_KEY = "change-me"

# Generate unique run ID for this demo execution
RUN_ID = int(time.time())

# Customer Profiles
CUSTOMER_PROFILES = [
    {
        "user_ref": "customer-001",
        "name": "Sarah Johnson",
        "profile_type": "conservative",
        "monthly_income": 5500,
        "avg_spending": 3800,
        "description": "Conservative saver with stable income"
    },
    {
        "user_ref": "customer-002",
        "name": "Michael Chen",
        "profile_type": "balanced",
        "monthly_income": 7200,
        "avg_spending": 6000,
        "description": "Balanced spender with good financial habits"
    },
    {
        "user_ref": "customer-003",
        "name": "Emily Rodriguez",
        "profile_type": "spender",
        "monthly_income": 6800,
        "avg_spending": 6500,
        "description": "High spender with entertainment focus"
    },
    {
        "user_ref": "customer-004",
        "name": "David Kim",
        "profile_type": "student",
        "monthly_income": 2800,
        "avg_spending": 2600,
        "description": "Student with tight budget"
    },
    {
        "user_ref": "customer-005",
        "name": "Jessica Williams",
        "profile_type": "freelancer",
        "monthly_income": 5200,
        "avg_spending": 4200,
        "description": "Freelancer with variable income"
    },
    {
        "user_ref": "customer-006",
        "name": "Robert Thompson",
        "profile_type": "business_owner",
        "monthly_income": 12000,
        "avg_spending": 9000,
        "description": "Small business owner with high transactions"
    },
    {
        "user_ref": "customer-007",
        "name": "Amanda Garcia",
        "profile_type": "family",
        "monthly_income": 8500,
        "avg_spending": 7800,
        "description": "Family with children, high grocery/education spending"
    },
    {
        "user_ref": "customer-008",
        "name": "James Martinez",
        "profile_type": "traveler",
        "monthly_income": 9000,
        "avg_spending": 8200,
        "description": "Travel enthusiast with frequent vacation spending"
    },
    {
        "user_ref": "customer-009",
        "name": "Lisa Anderson",
        "profile_type": "minimalist",
        "monthly_income": 6000,
        "avg_spending": 3500,
        "description": "Minimalist lifestyle with low spending"
    },
    {
        "user_ref": "customer-010",
        "name": "Christopher Lee",
        "profile_type": "investor",
        "monthly_income": 11000,
        "avg_spending": 6500,
        "description": "Investor with substantial savings and investments"
    }
]

# Transaction categories by profile type
CATEGORY_WEIGHTS = {
    "conservative": {
        "Groceries": 0.25,
        "Utilities": 0.15,
        "Transportation": 0.10,
        "Healthcare": 0.10,
        "Savings": 0.20,
        "Insurance": 0.10,
        "Shopping": 0.05,
        "Entertainment": 0.05
    },
    "balanced": {
        "Groceries": 0.20,
        "Utilities": 0.12,
        "Transportation": 0.12,
        "Dining": 0.15,
        "Entertainment": 0.10,
        "Shopping": 0.13,
        "Savings": 0.10,
        "Healthcare": 0.08
    },
    "spender": {
        "Shopping": 0.25,
        "Entertainment": 0.20,
        "Dining": 0.20,
        "Travel": 0.15,
        "Groceries": 0.10,
        "Transportation": 0.05,
        "Utilities": 0.05
    },
    "student": {
        "Groceries": 0.25,
        "Dining": 0.20,
        "Transportation": 0.15,
        "Entertainment": 0.15,
        "Education": 0.15,
        "Utilities": 0.10
    },
    "freelancer": {
        "Utilities": 0.15,
        "Groceries": 0.15,
        "Transportation": 0.10,
        "Dining": 0.12,
        "Shopping": 0.12,
        "Business": 0.15,
        "Entertainment": 0.11,
        "Healthcare": 0.10
    },
    "business_owner": {
        "Business": 0.30,
        "Dining": 0.15,
        "Transportation": 0.12,
        "Groceries": 0.10,
        "Shopping": 0.10,
        "Utilities": 0.08,
        "Entertainment": 0.08,
        "Travel": 0.07
    },
    "family": {
        "Groceries": 0.30,
        "Education": 0.18,
        "Healthcare": 0.12,
        "Utilities": 0.12,
        "Transportation": 0.10,
        "Entertainment": 0.08,
        "Dining": 0.05,
        "Shopping": 0.05
    },
    "traveler": {
        "Travel": 0.35,
        "Dining": 0.15,
        "Entertainment": 0.12,
        "Shopping": 0.12,
        "Groceries": 0.10,
        "Transportation": 0.08,
        "Utilities": 0.08
    },
    "minimalist": {
        "Groceries": 0.30,
        "Utilities": 0.20,
        "Transportation": 0.15,
        "Healthcare": 0.12,
        "Savings": 0.15,
        "Dining": 0.05,
        "Entertainment": 0.03
    },
    "investor": {
        "Investment": 0.30,
        "Savings": 0.15,
        "Groceries": 0.12,
        "Utilities": 0.10,
        "Dining": 0.10,
        "Transportation": 0.08,
        "Entertainment": 0.08,
        "Shopping": 0.07
    }
}


def generate_transactions(profile: Dict[str, Any], num_months: int = 3) -> List[Dict[str, Any]]:
    """Generate realistic transactions for a customer profile."""
    transactions = []
    user_ref = profile["user_ref"]
    profile_type = profile["profile_type"]
    monthly_income = profile["monthly_income"]
    avg_spending = profile["avg_spending"]
    
    # Get category weights for this profile
    category_weights = CATEGORY_WEIGHTS.get(profile_type, CATEGORY_WEIGHTS["balanced"])
    categories = list(category_weights.keys())
    weights = list(category_weights.values())
    
    start_date = datetime.now() - timedelta(days=num_months * 30)
    
    # Generate income transactions (1-2 per month)
    for month in range(num_months):
        income_date = start_date + timedelta(days=month * 30 + random.randint(1, 5))
        
        # Primary income
        transactions.append({
            "external_tx_id": f"{user_ref}-{RUN_ID}-income-{month}-1",
            "user_ref": user_ref,
            "occurred_at": income_date.isoformat(),
            "amount": f"{(monthly_income + random.uniform(-200, 200)):.2f}",
            "direction": "income",
            "category": "Salary",
            "description": "Monthly salary deposit",
            "currency": "USD"
        })
        
        # Occasional secondary income for some profiles
        if profile_type in ["freelancer", "business_owner", "investor"] and random.random() > 0.5:
            secondary_date = income_date + timedelta(days=random.randint(5, 20))
            transactions.append({
                "external_tx_id": f"{user_ref}-{RUN_ID}-income-{month}-2",
                "user_ref": user_ref,
                "occurred_at": secondary_date.isoformat(),
                "amount": f"{(monthly_income * random.uniform(0.2, 0.5)):.2f}",
                "direction": "income",
                "category": "Business" if profile_type == "business_owner" else "Investment",
                "description": "Additional income",
                "currency": "USD"
            })
    
    # Generate expense transactions (15-45 per month)
    num_expenses_per_month = {
        "conservative": 20,
        "balanced": 25,
        "spender": 35,
        "student": 22,
        "freelancer": 28,
        "business_owner": 45,
        "family": 40,
        "traveler": 30,
        "minimalist": 15,
        "investor": 25
    }.get(profile_type, 25)
    
    for month in range(num_months):
        month_start = start_date + timedelta(days=month * 30)
        num_expenses = num_expenses_per_month + random.randint(-5, 5)
        
        for i in range(num_expenses):
            expense_date = month_start + timedelta(
                days=random.randint(0, 29),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            category = random.choices(categories, weights=weights)[0]
            
            # Calculate amount based on category and profile
            base_amount = (avg_spending / num_expenses_per_month) * random.uniform(0.3, 2.5)
            
            # Some categories have higher amounts
            if category in ["Travel", "Business", "Investment"]:
                base_amount *= random.uniform(1.5, 3.0)
            elif category in ["Groceries", "Utilities", "Insurance"]:
                base_amount *= random.uniform(0.8, 1.2)
            
            # Add some large anomalous transactions occasionally
            if random.random() > 0.92:  # ~8% anomaly rate
                base_amount *= random.uniform(2.5, 4.0)
                # Some anomalies at night
                if random.random() > 0.6:
                    expense_date = expense_date.replace(hour=random.randint(22, 23))
            
            # Ensure amount is positive and format as string
            amount = max(0.01, round(base_amount, 2))
            
            # Generate description based on category
            descriptions = {
                "Groceries": ["Supermarket", "Whole Foods", "Trader Joe's", "Local market"],
                "Utilities": ["Electric bill", "Water bill", "Internet", "Phone bill"],
                "Transportation": ["Gas station", "Uber", "Public transit", "Car maintenance"],
                "Dining": ["Restaurant", "Coffee shop", "Fast food", "Food delivery"],
                "Entertainment": ["Movie theater", "Streaming service", "Concert", "Gaming"],
                "Shopping": ["Online shopping", "Clothing store", "Electronics", "Home goods"],
                "Healthcare": ["Pharmacy", "Doctor visit", "Gym membership", "Health insurance"],
                "Travel": ["Flight booking", "Hotel", "Vacation package", "Car rental"],
                "Education": ["Tuition", "Books", "Online course", "School supplies"],
                "Business": ["Office supplies", "Software subscription", "Client meeting", "Equipment"],
                "Savings": ["Transfer to savings", "Investment account", "Emergency fund"],
                "Insurance": ["Auto insurance", "Home insurance", "Life insurance"],
                "Investment": ["Stock purchase", "Mutual fund", "Retirement account", "Crypto"],
                "Debt": ["Credit card payment", "Loan payment", "Mortgage"]
            }
            
            description = random.choice(descriptions.get(category, ["Expense"]))
            
            transactions.append({
                "external_tx_id": f"{user_ref}-{RUN_ID}-expense-{month}-{i}",
                "user_ref": user_ref,
                "occurred_at": expense_date.isoformat(),
                "amount": f"{amount:.2f}",
                "direction": "expense",
                "category": category,
                "description": description,
                "currency": "USD"
            })
    
    return sorted(transactions, key=lambda x: x["occurred_at"])


def ingest_transactions(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ingest transactions via API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/ingest/transactions",
            headers={
                "X-INGEST-KEY": INGEST_KEY,
                "Content-Type": "application/json"
            },
            json={"transactions": transactions},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        # Try to get detailed error from response
        try:
            error_detail = response.json()
            print(f"❌ Error ingesting transactions: {e}")
            print(f"   API Response: {error_detail}")
            return {"status": "error", "message": str(e), "detail": error_detail}
        except:
            print(f"❌ Error ingesting transactions: {e}")
            print(f"   Response text: {response.text[:500]}")
            return {"status": "error", "message": str(e)}
    except requests.exceptions.RequestException as e:
        print(f"❌ Error ingesting transactions: {e}")
        return {"status": "error", "message": str(e)}


def fetch_user_summary(user_ref: str) -> Dict[str, Any]:
    """Fetch user summary report."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/users/{user_ref}/reports/summary",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def fetch_fhs(user_ref: str) -> Dict[str, Any]:
    """Fetch Financial Health Score."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/users/{user_ref}/reports/fhs",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def fetch_behavior_profile(user_ref: str) -> Dict[str, Any]:
    """Fetch behavior profile."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/users/{user_ref}/reports/behavior-profile",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def fetch_anomalies(user_ref: str) -> Dict[str, Any]:
    """Fetch anomaly report."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/users/{user_ref}/reports/anomalies",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def fetch_recommendations(user_ref: str) -> Dict[str, Any]:
    """Fetch recommendations."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/users/{user_ref}/reports/recommendations",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def fetch_recent_expense_transactions(user_ref: str, limit: int = 5) -> Dict[str, Any]:
    """Fetch recent expense transactions for xAI scoring preview."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/users/{user_ref}/transactions",
            params={"direction": "expense", "limit": limit, "offset": 0},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def fetch_batch_prediction(user_ref: str, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run batch anomaly prediction with xAI for given transactions."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/users/{user_ref}/reports/anomaly-predict-batch",
            json={"transactions": transactions},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def display_customer_analysis(profile: Dict[str, Any]):
    """Display comprehensive analysis for a customer."""
    user_ref = profile["user_ref"]
    name = profile["name"]
    description = profile["description"]
    
    print(f"\n{'='*80}")
    print(f"📊 CUSTOMER ANALYSIS: {name} ({user_ref})")
    print(f"{'='*80}")
    print(f"Profile: {description}\n")
    
    # 1. Summary Report
    print("📈 TRANSACTION SUMMARY")
    print("-" * 80)
    summary = fetch_user_summary(user_ref)
    if "error" not in summary:
        income_total = float(summary.get('income_total', 0) or 0)
        expense_total = float(summary.get('expense_total', 0) or 0)
        net_total = float(summary.get('net_total', income_total - expense_total) or 0)
        savings_rate = ((net_total / income_total) * 100) if income_total > 0 else 0.0

        print(f"  Total Income: ${income_total:,.2f}")
        print(f"  Total Expenses: ${expense_total:,.2f}")
        print(f"  Net Savings: ${net_total:,.2f}")
        print(f"  Savings Rate: {savings_rate:.1f}%")

        tx_preview = fetch_recent_expense_transactions(user_ref, limit=1)
        if "error" not in tx_preview:
            print(f"  Transaction Count (API): {tx_preview.get('total', 0)}")
    else:
        print(f"  ⚠️  Error fetching summary: {summary['error']}")
    
    # 2. Financial Health Score
    print(f"\n💰 FINANCIAL HEALTH SCORE (FHS)")
    print("-" * 80)
    fhs = fetch_fhs(user_ref)
    if "error" not in fhs:
        score = float(fhs.get('score', 0) or 0)
        rating = fhs.get('interpretation', 'N/A')
        
        # Color-coded display
        if rating == "Excellent":
            icon = "🟢"
        elif rating == "Good":
            icon = "🟡"
        elif rating == "Fair":
            icon = "🟠"
        else:
            icon = "🔴"
        
        print(f"  {icon} Score: {score:.1f}/100 - Rating: {rating}")
        
        subscores = fhs.get('subscores', [])
        if subscores:
            print("\n  Score Breakdown:")
            for component in subscores[:4]:
                print(
                    f"    • {component.get('name', 'Component')}: "
                    f"{float(component.get('score', 0) or 0):.1f}/"
                    f"{float(component.get('max_score', 0) or 0):.0f}"
                )
    else:
        print(f"  ⚠️  Error fetching FHS: {fhs['error']}")
    
    # 3. Behavior Profile
    print(f"\n👤 BEHAVIOR PROFILE")
    print("-" * 80)
    profile_data = fetch_behavior_profile(user_ref)
    if "error" not in profile_data:
        profile_label = profile_data.get('profile_name', 'Unknown')
        profile_desc = profile_data.get('description', 'N/A')
        confidence = profile_data.get('confidence_score', 0)
        
        print(f"  Profile Type: {profile_label}")
        print(f"  Description: {profile_desc}")
        print(f"  Confidence: {confidence:.1%}")
        
        characteristics = profile_data.get('key_traits', [])
        if characteristics:
            print("\n  Key Characteristics:")
            for char in characteristics:
                print(f"    • {char}")
    else:
        print(f"  ⚠️  Error fetching profile: {profile_data['error']}")
    
    # 4. Anomalies + xAI scoring preview
    print(f"\n⚠️  ANOMALY DETECTION")
    print("-" * 80)
    anomalies = fetch_anomalies(user_ref)
    if "error" not in anomalies:
        anomaly_list = anomalies.get('items', [])
        if anomaly_list:
            print(f"  Found {len(anomaly_list)} anomalies:\n")
            for idx, anom in enumerate(anomaly_list[:5], 1):  # Show top 5
                print(f"  {idx}. Transaction ID: {anom.get('transaction_id', 'N/A')}")
                print(f"     Type: {anom.get('type', 'N/A')}")
                print(f"     Amount: ${float(anom.get('amount', 0) or 0):,.2f}")
                print(f"     Category: {anom.get('category', 'N/A')}")
                print(f"     Date: {anom.get('occurred_at', 'N/A')[:10]}")
                print(f"     Score: {float(anom.get('score', 0) or 0):.3f}")
                print(f"     Reason: {anom.get('reason', 'N/A')}")
                print()
                
            if len(anomaly_list) > 5:
                print(f"  ... and {len(anomaly_list) - 5} more anomalies")
        else:
            print("  ✅ No high-risk transactions detected")
    else:
        print(f"  ⚠️  Error fetching anomalies: {anomalies['error']}")

    print(f"\n🔍 xAI EXPLANATION PREVIEW (per customer)")
    print("-" * 80)
    recent_tx = fetch_recent_expense_transactions(user_ref, limit=3)
    if "error" in recent_tx:
        print(f"  ⚠️  Could not fetch recent transactions for xAI: {recent_tx['error']}")
    else:
        items = recent_tx.get("items", [])
        if not items:
            print("  ⚠️  No recent expense transactions available for xAI preview")
        else:
            batch_payload = [
                {
                    "occurred_at": tx["occurred_at"],
                    "amount": str(tx["amount"]),
                    "direction": tx.get("direction", "expense"),
                    "category": tx.get("category"),
                    "description": tx.get("description"),
                    "currency": tx.get("currency") or "USD",
                }
                for tx in items
            ]
            scored = fetch_batch_prediction(user_ref, batch_payload)
            if "error" in scored:
                print(f"  ⚠️  xAI scoring failed: {scored['error']}")
            else:
                predictions = scored.get("predictions", [])
                if not predictions:
                    print("  ⚠️  No xAI predictions returned")
                else:
                    for idx, pred in enumerate(predictions, start=1):
                        print(
                            f"  {idx}. ${float(pred.get('amount', 0) or 0):,.2f} "
                            f"| {pred.get('category', 'N/A')} "
                            f"| risk={float(pred.get('risk_score', 0) or 0):.3f} "
                            f"| {'🔴 HIGH' if pred.get('predicted_is_high_risk') else '🟢 LOW'}"
                        )
                        factors = pred.get("xai_factors", [])
                        if factors:
                            for factor in factors[:3]:
                                print(
                                    f"      • {factor.get('feature', 'feature')}: "
                                    f"{float(factor.get('contribution', 0) or 0):.3f} "
                                    f"({factor.get('effect', 'risk_up')})"
                                )
    
    # 5. Recommendations
    print(f"\n💡 PERSONALIZED RECOMMENDATIONS")
    print("-" * 80)
    recommendations = fetch_recommendations(user_ref)
    if "error" not in recommendations:
        rec_list = recommendations.get('items', [])
        if rec_list:
            for rec in rec_list:
                priority = rec.get('priority', 'medium')
                icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
                print(f"  {icon} [{priority.upper()}] {rec.get('title', 'General')}")
                print(f"     {rec.get('message', 'N/A')}")
                print(f"     Impact: {rec.get('estimated_impact', 'N/A')}")
                print()
        else:
            print("  ✅ No specific recommendations at this time")
    else:
        print(f"  ⚠️  Error fetching recommendations: {recommendations['error']}")


def manual_prediction_demo():
    """Demonstrate manual batch prediction feature."""
    print(f"\n{'='*80}")
    print("🔮 BATCH PREDICTION DEMO")
    print("="*80)
    print("Testing batch anomaly prediction with manual transaction scenarios...\n")
    
    # Use first customer for demo
    demo_user = CUSTOMER_PROFILES[0]["user_ref"]
    
    # Scenario 1: High-risk late-night shopping spree
    print("📝 Scenario 1: Late-night shopping spree")
    print("-" * 80)
    
    test_transactions_1 = [
        {
            "amount": 850.00,
            "category": "Shopping",
            "occurred_at": "2024-03-06T23:45:00",
            "direction": "expense",
            "description": "Late night online shopping"
        },
        {
            "amount": 320.00,
            "category": "Entertainment",
            "occurred_at": "2024-03-06T23:52:00",
            "direction": "expense",
            "description": "Gaming purchase"
        },
        {
            "amount": 450.00,
            "category": "Shopping",
            "occurred_at": "2024-03-07T00:15:00",
            "direction": "expense",
            "description": "Electronics"
        }
    ]
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/users/{demo_user}/reports/anomaly-predict-batch",
            json={"transactions": test_transactions_1},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        predictions = result.get('predictions', [])
        for idx, pred in enumerate(predictions, 1):
            print(f"\n  Transaction {idx}:")
            amount = float(pred.get('amount', 0))
            print(f"    Amount: ${amount:,.2f} | Category: {pred.get('category', 'N/A')}")
            print(f"    Risk Score: {pred.get('risk_score', 0):.3f}")
            print(f"    Prediction: {'🔴 HIGH RISK' if pred.get('is_high_risk') else '🟢 Low Risk'}")
            
            xai = pred.get('xai_factors', [])
            if xai:
                print(f"    🔍 Key Risk Factors:")
                for factor in xai[:2]:
                    print(f"       • {factor['feature']}: {factor['contribution']:.3f} ({factor['effect']})")
        
        recs = result.get('recommendations', [])
        if recs:
            print(f"\n  💡 Recommendations:")
            for rec in recs:
                print(f"    • [{rec.get('priority', 'medium').upper()}] {rec.get('message', 'N/A')}")
    
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error: {e}")
    
    # Scenario 2: Normal daily expenses
    print(f"\n\n📝 Scenario 2: Regular daily expenses")
    print("-" * 80)
    
    test_transactions_2 = [
        {
            "amount": 45.00,
            "category": "Groceries",
            "occurred_at": "2024-03-07T10:30:00",
            "direction": "expense",
            "description": "Weekly groceries"
        },
        {
            "amount": 12.50,
            "category": "Dining",
            "occurred_at": "2024-03-07T12:15:00",
            "direction": "expense",
            "description": "Lunch"
        },
        {
            "amount": 35.00,
            "category": "Transportation",
            "occurred_at": "2024-03-07T17:00:00",
            "direction": "expense",
            "description": "Gas"
        }
    ]
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/users/{demo_user}/reports/anomaly-predict-batch",
            json={"transactions": test_transactions_2},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        predictions = result.get('predictions', [])
        for idx, pred in enumerate(predictions, 1):
            print(f"\n  Transaction {idx}:")
            amount = float(pred.get('amount', 0))
            print(f"    Amount: ${amount:,.2f} | Category: {pred.get('category', 'N/A')}")
            print(f"    Risk Score: {pred.get('risk_score', 0):.3f}")
            print(f"    Prediction: {'🔴 HIGH RISK' if pred.get('is_high_risk') else '🟢 Low Risk'}")
        
        recs = result.get('recommendations', [])
        if recs:
            print(f"\n  💡 Recommendations:")
            for rec in recs:
                print(f"    • [{rec.get('priority', 'medium').upper()}] {rec.get('message', 'N/A')}")
        else:
            print(f"\n  ✅ No concerning patterns detected")
    
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error: {e}")


def main():
    """Main demo execution."""
    print("\n" + "="*80)
    print("🏦 TrustiPay Financial Analyst Demo")
    print("="*80)
    print("\nThis demo simulates a financial analyst managing 10 diverse customers.")
    print("Each customer has a unique financial profile and transaction history.")
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Number of customers: {len(CUSTOMER_PROFILES)}")
    print(f"Run ID: {RUN_ID} (ensures unique transactions per run)")
    print("="*80)
    
    # Check API connectivity
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
        print("✅ API connection successful\n")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        print(f"Please ensure the backend is running on {API_BASE_URL}")
        sys.exit(1)
    
    # Phase 1: Transaction Ingestion
    print("\n" + "="*80)
    print("📥 PHASE 1: TRANSACTION INGESTION")
    print("="*80)
    
    total_ingested = 0
    for idx, profile in enumerate(CUSTOMER_PROFILES, 1):
        user_ref = profile["user_ref"]
        name = profile["name"]
        
        print(f"\n[{idx}/{len(CUSTOMER_PROFILES)}] Generating transactions for {name} ({user_ref})...")
        
        transactions = generate_transactions(profile, num_months=3)
        print(f"  Generated {len(transactions)} transactions")
        
        print(f"  Ingesting transactions...")
        result = ingest_transactions(transactions)
        
        # Check if ingestion was successful (API returns 'inserted' field on success)
        if "inserted" in result:
            inserted = result.get("inserted", 0)
            duplicates = result.get("duplicates", 0)
            failed = result.get("failed", 0)
            print(f"  ✅ Success: {inserted} inserted, {duplicates} duplicates, {failed} failed")
            total_ingested += inserted
        else:
            print(f"  ❌ Failed: {result.get('message', 'Unknown error')}")
    
    print(f"\n{'='*80}")
    print(f"✅ Ingestion complete! Total transactions ingested: {total_ingested}")
    print("="*80)
    
    # Phase 2: Customer Analysis
    print("\n" + "="*80)
    print("📊 PHASE 2: COMPREHENSIVE CUSTOMER ANALYSIS")
    print("="*80)
    
    for idx, profile in enumerate(CUSTOMER_PROFILES, 1):
        print(f"\n[{idx}/{len(CUSTOMER_PROFILES)}]")
        display_customer_analysis(profile)
        
        # Pause between customers for readability
        if idx < len(CUSTOMER_PROFILES):
            print("\n➜ Moving to next customer analysis...")
    
    # Phase 3: Manual Prediction Demo
    print("\n" + "="*80)
    print("🔮 PHASE 3: BATCH PREDICTION CAPABILITY")
    print("="*80)
    print("\n➜ Running batch prediction demo...")
    
    manual_prediction_demo()
    
    # Summary
    print("\n" + "="*80)
    print("✅ DEMO COMPLETE")
    print("="*80)
    print("\n📋 Summary:")
    print(f"  • Successfully created {len(CUSTOMER_PROFILES)} customers")
    print(f"  • Ingested {total_ingested} transactions")
    print(f"  • Generated comprehensive analytics for all customers")
    print(f"  • Demonstrated batch prediction capability")
    
    print("\n💡 Next Steps:")
    print("  1. Open the Streamlit dashboard: streamlit run dashboard/dashboard.py")
    print("  2. Select any customer from the dropdown (customer-001 to customer-010)")
    print("  3. Explore all tabs: Overview, Transactions, Reports, FHS, Profile, Recommendations")
    print("  4. Test the 'Batch Predict' tab with custom transactions")
    
    print("\n🎯 All customers are now available in the system!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
