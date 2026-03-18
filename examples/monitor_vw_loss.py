#!/usr/bin/env python3
"""
Monitor VW's loss function to verify the model is learning.
Lower loss over iterations indicates learning.
"""

from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback
import numpy as np


def monitor_learning_loss():
    """Track VW's loss function to verify learning."""
    
    bandit = ContextualBanditFeedback(dim=602)
    
    losses = []
    num_iterations = 50
    
    print("Monitoring VW Loss Function\n")
    print(f"{'Iteration':<12} {'Loss':<15} {'Avg Loss (5)':<15}")
    print("-" * 42)
    
    for i in range(num_iterations):
        # Generate synthetic interaction
        vector = np.random.randn(602)
        vector = vector / np.linalg.norm(vector)
        
        # Alternate between likes and dislikes to create pattern
        reward = 1 if i % 3 == 0 else 0
        
        # Get prediction before update
        pred = bandit.predict_preference(vector)
        loss = (pred - reward) ** 2  # Simple squared error
        losses.append(loss)
        
        # Update model
        bandit.update(vector, reward=reward)
        
        if (i + 1) % 10 == 0:
            avg_loss = np.mean(losses[-5:])
            print(f"{i+1:<12} {loss:<15.6f} {avg_loss:<15.6f}")
    
    # Summary statistics
    initial_loss = np.mean(losses[:10])
    final_loss = np.mean(losses[-10:])
    improvement = ((initial_loss - final_loss) / initial_loss * 100) if initial_loss > 0 else 0
    
    print("\n" + "=" * 50)
    print(f"Initial Loss (first 10 iterations): {initial_loss:.6f}")
    print(f"Final Loss (last 10 iterations):    {final_loss:.6f}")
    print(f"Improvement:                         {improvement:.2f}%")
    print("=" * 50)
    
    if final_loss < initial_loss:
        print("\n✅ MODEL IS LEARNING - Loss decreased!")
        print(f"   The model reduced prediction error by {improvement:.2f}%")
        return True
    else:
        print("\n⚠️  Loss did not decrease. Check model configuration.")
        return False


if __name__ == "__main__":
    try:
        import matplotlib.pyplot as plt
        monitor_learning_loss_with_plot()
    except ImportError:
        print("matplotlib not installed. Running without plot visualization.\n")
        monitor_learning_loss()


def monitor_learning_loss_with_plot():
    """Monitor loss with optional matplotlib visualization."""
    
    bandit = ContextualBanditFeedback(dim=602)
    
    losses = []
    num_iterations = 100
    
    print("Monitoring VW Loss Function with Visualization\n")
    
    for i in range(num_iterations):
        vector = np.random.randn(602)
        vector = vector / np.linalg.norm(vector)
        reward = 1 if i % 3 == 0 else 0
        
        pred = bandit.predict_preference(vector)
        loss = (pred - reward) ** 2
        losses.append(loss)
        
        bandit.update(vector, reward=reward)
        
        if (i + 1) % 20 == 0:
            print(f"Iteration {i+1:3d} | Loss: {loss:.6f}")
    
    # Plot results
    import matplotlib.pyplot as plt
    
    plt.figure(figsize=(12, 6))
    plt.plot(losses, linewidth=2, label='Prediction Loss')
    
    initial_avg = np.mean(losses[:10])
    final_avg = np.mean(losses[-10:])
    
    plt.axhline(y=initial_avg, color='r', linestyle='--', linewidth=2, label=f'Initial Avg Loss: {initial_avg:.4f}')
    plt.axhline(y=final_avg, color='g', linestyle='--', linewidth=2, label=f'Final Avg Loss: {final_avg:.4f}')
    
    plt.xlabel('Iteration', fontsize=12)
    plt.ylabel('Loss (Squared Error)', fontsize=12)
    plt.title('VW Model Learning - Loss Over Time', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    
    plot_path = '/tmp/vw_learning_loss.png'
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    print(f"\n✅ Loss plot saved to {plot_path}")
    
    improvement = ((initial_avg - final_avg) / initial_avg * 100) if initial_avg > 0 else 0
    print(f"\nInitial Loss (first 10 iterations): {initial_avg:.6f}")
    print(f"Final Loss (last 10 iterations):   {final_avg:.6f}")
    print(f"Improvement:                        {improvement:.2f}%")
    
    if final_avg < initial_avg:
        print("\n✅ MODEL IS LEARNING - Loss decreased!")
    else:
        print("\n⚠️  Loss did not decrease")
