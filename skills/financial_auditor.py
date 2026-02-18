import csv
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import os


class FinancialAuditor:
    """
    Simulates reading bank statements to identify revenue and software subscriptions,
    and implements weekly audit logic to detect unused subscriptions or cost increases.
    """
    
    def __init__(self, csv_file_path):
        self.csv_file_path = csv_file_path
        self.transactions = []
        self.software_subscriptions = {}
        self.revenue_data = []
        
    def load_transactions(self):
        """Load transactions from CSV file"""
        try:
            df = pd.read_csv(self.csv_file_path)
            self.transactions = df.to_dict('records')
            print(f"Loaded {len(self.transactions)} transactions from {self.csv_file_path}")
            return True
        except Exception as e:
            print(f"Error loading transactions: {e}")
            return False
    
    def categorize_transactions(self):
        """Categorize transactions into subscriptions and revenue"""
        for transaction in self.transactions:
            desc = transaction['description'].lower()
            
            # Identify software subscriptions
            if any(sub in desc for sub in ['subscription', 'notion', 'slack', 'github', 'zoom', 'adobe', 'microsoft', 'google workspace']):
                service_name = self._extract_service_name(desc)
                
                if service_name not in self.software_subscriptions:
                    self.software_subscriptions[service_name] = {
                        'transactions': [],
                        'total_spent': 0,
                        'frequency': 0,
                        'avg_cost': 0
                    }
                
                self.software_subscriptions[service_name]['transactions'].append(transaction)
                self.software_subscriptions[service_name]['total_spent'] += abs(float(transaction['amount']))
                self.software_subscriptions[service_name]['frequency'] += 1
                
            # Identify revenue
            elif transaction['type'] == 'revenue':
                self.revenue_data.append(transaction)
    
    def _extract_service_name(self, description):
        """Extract service name from description"""
        description_lower = description.lower()
        if 'notion' in description_lower:
            return 'Notion'
        elif 'slack' in description_lower:
            return 'Slack'
        elif 'github' in description_lower:
            return 'GitHub'
        elif 'zoom' in description_lower:
            return 'Zoom'
        elif 'adobe' in description_lower:
            return 'Adobe'
        elif 'google workspace' in description_lower or 'workspace' in description_lower:
            return 'Google Workspace'
        elif 'amazon web services' in description_lower or 'aws' in description_lower:
            return 'AWS'
        else:
            return description.title()
    
    def weekly_audit_logic(self):
        """Implement weekly audit logic to identify unused subscriptions or cost increases"""
        audit_findings = {
            'unused_subscriptions': [],
            'cost_increases': [],
            'high_frequency_transactions': [],
            'anomalies': []
        }
        
        for service, data in self.software_subscriptions.items():
            transactions = data['transactions']
            
            # Calculate average cost
            total_amount = sum(abs(float(t['amount'])) for t in transactions)
            data['avg_cost'] = total_amount / len(transactions) if transactions else 0
            
            # Check for potential unused subscriptions (based on usage patterns)
            dates = [datetime.strptime(t['date'], '%Y-%m-%d') for t in transactions]
            date_range = max(dates) - min(dates) if dates else timedelta(days=0)
            
            # If subscription has been paid for but no corresponding usage data (in a real system)
            # For simulation, we'll flag if there are multiple payments close together without variation
            if len(transactions) > 1:
                amounts = [float(t['amount']) for t in transactions]
                if len(set(amounts)) == 1:  # All payments are the same amount
                    # Check if payments are regular (could indicate ongoing subscription)
                    sorted_dates = sorted(dates)
                    intervals = [(sorted_dates[i+1] - sorted_dates[i]).days for i in range(len(sorted_dates)-1)]
                    
                    # If intervals are roughly monthly (25-35 days), it's likely a regular subscription
                    if intervals and all(25 <= interval <= 35 for interval in intervals):
                        # In a real system, we would check for usage data here
                        # For simulation, we'll note this as a potentially unused subscription
                        audit_findings['unused_subscriptions'].append({
                            'service': service,
                            'monthly_cost': abs(float(transactions[0]['amount'])),
                            'payment_frequency': 'monthly',
                            'last_payment_date': max(dates).strftime('%Y-%m-%d'),
                            'note': 'Regular monthly payment detected; no usage data available to confirm activity'
                        })
            
            # Check for cost increases
            if len(transactions) > 1:
                amounts = [abs(float(t['amount'])) for t in transactions]
                if amounts and max(amounts) > min(amounts) * 1.1:  # More than 10% increase
                    audit_findings['cost_increases'].append({
                        'service': service,
                        'previous_cost': min(amounts),
                        'current_cost': max(amounts),
                        'increase_percentage': round(((max(amounts) - min(amounts)) / min(amounts)) * 100, 2)
                    })
        
        return audit_findings
    
    def generate_ceo_briefing(self, output_path):
        """Generate a Monday Morning CEO Briefing"""
        if not self.load_transactions():
            return False
            
        self.categorize_transactions()
        audit_findings = self.weekly_audit_logic()
        
        # Calculate revenue summary
        total_revenue = sum(float(r['amount']) for r in self.revenue_data)
        total_expenses = sum(abs(float(t['amount'])) for t in self.transactions if t['type'] == 'expense')
        net_income = total_revenue + total_expenses  # Expenses are negative values
        
        # Prepare briefing content
        briefing_content = f"""# Monday Morning CEO Briefing
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Generated by:** AI Employee Zoya - Financial Auditor

## Revenue Summary
- Total Revenue: ${total_revenue:,.2f}
- Total Expenses: ${abs(total_expenses):,.2f}
- Net Income: ${net_income:,.2f}
- Number of Revenue Transactions: {len(self.revenue_data)}

## Software Subscriptions Overview
- Total Active Subscriptions: {len(self.software_subscriptions)}
- Monthly Recurring Costs: ${sum(data['avg_cost'] for data in self.software_subscriptions.values()):,.2f}

### Subscription Details:
"""
        
        for service, data in self.software_subscriptions.items():
            briefing_content += f"- {service}: ${data['avg_cost']:,.2f}/month (used {data['frequency']} times)\n"
        
        briefing_content += "\n## Bottlenecks\n"
        
        if audit_findings['unused_subscriptions']:
            briefing_content += "### Potentially Unused Subscriptions:\n"
            for sub in audit_findings['unused_subscriptions']:
                briefing_content += f"- {sub['service']}: ${sub['monthly_cost']:.2f}/month - {sub['note']}\n"
        else:
            briefing_content += "- No potentially unused subscriptions detected.\n"
        
        if audit_findings['cost_increases']:
            briefing_content += "\n### Cost Increases:\n"
            for inc in audit_findings['cost_increases']:
                briefing_content += f"- {inc['service']}: Increased from ${inc['previous_cost']:.2f} to ${inc['current_cost']:.2f} ({inc['increase_percentage']}%)\n"
        else:
            briefing_content += "- No significant cost increases detected.\n"
        
        briefing_content += "\n## Cost Optimization Suggestions\n"
        
        if audit_findings['unused_subscriptions']:
            briefing_content += "### Potential Savings:\n"
            total_potential_savings = sum(sub['monthly_cost'] for sub in audit_findings['unused_subscriptions'])
            briefing_content += f"- Cancel unused subscriptions: Up to ${total_potential_savings:.2f}/month savings\n"
            for sub in audit_findings['unused_subscriptions']:
                briefing_content += f"  - {sub['service']}: ${sub['monthly_cost']:.2f}/month\n"
        else:
            briefing_content += "- No unused subscriptions to cancel.\n"
        
        if audit_findings['cost_increases']:
            briefing_content += "\n- Review services with cost increases for necessity and negotiate better rates\n"
        else:
            briefing_content += "- No cost increases requiring review.\n"
        
        briefing_content += f"\n- Consider consolidating services if multiple tools serve similar functions\n"
        briefing_content += f"- Review annual subscription options for potential discounts\n\n"
        
        briefing_content += "---\n*This briefing was automatically generated by AI Employee Zoya's Financial Auditor skill.*\n"
        
        # Write the briefing to file
        with open(output_path, 'w') as f:
            f.write(briefing_content)
        
        print(f"CEO Briefing generated: {output_path}")
        return True


def main():
    """Main function to run the financial auditor"""
    csv_file = "workspace/bank_transactions.csv"
    output_path = "obsidian_vault/Briefings/ceo_briefing.md"
    
    auditor = FinancialAuditor(csv_file)
    success = auditor.generate_ceo_briefing(output_path)
    
    if success:
        print("Financial audit completed successfully!")
    else:
        print("Financial audit failed!")


if __name__ == "__main__":
    main()