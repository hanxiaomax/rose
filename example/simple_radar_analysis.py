#!/usr/bin/env python3
"""
Simple radar data analysis script
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

def main():
    """Main analysis function"""
    print("Loading radar data...")
    
    # Load the CSV file
    df = pd.read_csv('df.csv')
    print(f"Loaded {len(df)} rows")
    
    # Extract radar distance data
    radar_ranges = []
    
    # Get radar range data
    if 'range' in df.columns:
        ranges = df['range'].dropna()
        valid_ranges = ranges[(ranges > 0) & (ranges < 200)].tolist()
        radar_ranges.extend(valid_ranges)
    
    # Get radar track ranges
    track_range_cols = [col for col in df.columns if 'tracks[' in str(col) and 'range' in str(col)]
    for col in track_range_cols:
        ranges = df[col].dropna()
        valid_ranges = ranges[(ranges > 0) & (ranges < 200)].tolist()
        radar_ranges.extend(valid_ranges)
    
    print(f"Found {len(radar_ranges)} valid radar distance measurements")
    
    if not radar_ranges:
        print("No valid radar data found")
        return
    
    # Calculate statistics
    ranges = np.array(radar_ranges)
    stats = {
        'min': np.min(ranges),
        'max': np.max(ranges),
        'mean': np.mean(ranges),
        'median': np.median(ranges),
        'std': np.std(ranges),
        'count': len(ranges)
    }
    
    print("\n=== Radar Detection Distance Statistics ===")
    print(f"Minimum Distance: {stats['min']:.2f} meters")
    print(f"Maximum Distance: {stats['max']:.2f} meters")
    print(f"Mean Distance: {stats['mean']:.2f} meters")
    print(f"Median Distance: {stats['median']:.2f} meters")
    print(f"Standard Deviation: {stats['std']:.2f} meters")
    print(f"Total Samples: {stats['count']}")
    
    # Create simple visualization
    plt.figure(figsize=(12, 8))
    
    # Histogram
    plt.subplot(2, 2, 1)
    plt.hist(ranges, bins=20, alpha=0.7, color='blue', edgecolor='black')
    plt.axvline(stats['mean'], color='red', linestyle='--', label=f'Mean: {stats["mean"]:.1f}m')
    plt.xlabel('Distance (meters)')
    plt.ylabel('Count')
    plt.title('Radar Distance Distribution')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Time series
    plt.subplot(2, 2, 2)
    plt.plot(ranges, alpha=0.7, color='orange')
    plt.axhline(stats['mean'], color='red', linestyle='--', label='Mean')
    plt.axhline(stats['max'], color='green', linestyle=':', label=f'Max: {stats["max"]:.1f}m')
    plt.axhline(stats['min'], color='blue', linestyle=':', label=f'Min: {stats["min"]:.1f}m')
    plt.xlabel('Sample Index')
    plt.ylabel('Distance (meters)')
    plt.title('Radar Distance Over Time')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Box plot
    plt.subplot(2, 2, 3)
    plt.boxplot(ranges, vert=True)
    plt.ylabel('Distance (meters)')
    plt.title('Radar Distance Box Plot')
    plt.grid(True, alpha=0.3)
    
    # Statistics text
    plt.subplot(2, 2, 4)
    plt.axis('off')
    text = f"""
    Radar Detection Summary
    
    Min: {stats['min']:.1f} m
    Max: {stats['max']:.1f} m  
    Mean: {stats['mean']:.1f} m
    Median: {stats['median']:.1f} m
    Std: {stats['std']:.1f} m
    Count: {stats['count']}
    """
    plt.text(0.1, 0.9, text, fontsize=12, verticalalignment='top',
             bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))
    
    plt.suptitle('Radar Detection Distance Analysis', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig('radar.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("Visualization saved as radar.png")

if __name__ == "__main__":
    main()