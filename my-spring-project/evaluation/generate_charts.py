import matplotlib.pyplot as plt
import numpy as np
import os

# Create directory for charts if not exists
os.makedirs("charts", exist_ok=True)

# Set global style for presentation
plt.style.use('ggplot')
plt.rcParams.update({'font.size': 14, 'axes.titlesize': 18, 'axes.labelsize': 14})

# ==========================================
# 1. Search Quality (Precision@5) Bar Chart
# ==========================================
def plot_search_quality():
    labels = ['Ingredient-based', 'Nutrition-focused', 'Time-constrained', 'Average']
    epicure_scores = [0.85, 0.90, 0.80, 0.85]
    keyword_scores = [0.45, 0.35, 0.40, 0.40]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, epicure_scores, width, label='Epicure (LLM + Vector)', color='#2e86de')
    rects2 = ax.bar(x + width/2, keyword_scores, width, label='Keyword Only', color='#ff9f43')

    ax.set_ylabel('Precision@5 Score')
    ax.set_title('Search Quality Comparison (Higher is better)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.set_ylim(0, 1.1)

    # Add text labels
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontweight='bold')

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()
    plt.savefig('charts/search_quality_comparison.png', dpi=300)
    plt.close()
    print("Saved charts/search_quality_comparison.png")

# ==========================================
# 2. Stress Test Latency Line Chart
# ==========================================
def plot_stress_test():
    concurrent_users = [1, 5, 10, 20, 50]
    latency = [3.2, 5.8, 11.5, 18.2, 32.5]
    error_rate = [0, 0, 0, 2, 8]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot Latency
    color = '#ee5253'
    ax1.set_xlabel('Concurrent Users')
    ax1.set_ylabel('Average Latency (seconds)', color=color)
    ax1.plot(concurrent_users, latency, marker='o', linewidth=3, markersize=10, color=color, label='Latency')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_xticks(concurrent_users)
    
    # Add latency data labels
    for i, txt in enumerate(latency):
        ax1.annotate(f'{txt}s', (concurrent_users[i]-0.5, latency[i]+1), color=color, fontweight='bold')

    # Create a second y-axis for Error Rate
    ax2 = ax1.twinx()  
    color = '#222f3e'
    ax2.set_ylabel('Error Rate (%)', color=color)  
    ax2.plot(concurrent_users, error_rate, marker='s', linestyle='--', linewidth=2, markersize=8, color=color, label='Error Rate')
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.set_ylim(-2, 20)

    # Add error rate data labels
    for i, txt in enumerate(error_rate):
        ax2.annotate(f'{txt}%', (concurrent_users[i]+0.5, error_rate[i]-1), color=color, fontweight='bold')

    plt.title('System Performance Under Load')
    fig.tight_layout()
    plt.savefig('charts/stress_test_performance.png', dpi=300)
    plt.close()
    print("Saved charts/stress_test_performance.png")

# ==========================================
# 3. Fault Tolerance Bar Chart
# ==========================================
def plot_fault_tolerance():
    trials = ['Trial 1', 'Trial 2', 'Trial 3', 'Average']
    times = [5.2, 4.8, 5.6, 5.2]

    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Use a different color for the average bar
    colors = ['#10ac84', '#10ac84', '#10ac84', '#01a3a4']
    bars = ax.bar(trials, times, color=colors, width=0.6)

    ax.set_ylabel('Recovery Time (seconds)')
    ax.set_title('Leader Election Recovery Time')
    ax.set_ylim(0, 8)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}s',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), 
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')

    fig.tight_layout()
    plt.savefig('charts/fault_tolerance_recovery.png', dpi=300)
    plt.close()
    print("Saved charts/fault_tolerance_recovery.png")


if __name__ == "__main__":
    print("Generating evaluation charts...")
    plot_search_quality()
    plot_stress_test()
    plot_fault_tolerance()
    print("Done! Check the 'charts' folder.")
