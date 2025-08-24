#!/usr/bin/env python3
"""
Quick radar analysis and visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load data efficiently
df = pd.read_csv('df.csv', usecols=['topic', 'range', 'tracks[0].range', 'tracks[1].range', 'tracks[2].range', 'tracks[3].range', 'tracks[4].range'])

# Extract all radar ranges
all_ranges = []

# From range column for radar topics
radar_mask = df['topic'].str.contains('radar', na=False, case=False)
if radar_mask.any():
    radar_data = df[radar_mask]
    if 'range' in df.columns:
        ranges = radar_data['range'].dropna()
        valid = ranges[(ranges > 0) & (ranges < 200)].tolist()
        all_ranges.extend(valid)

# From track ranges
track_cols = ['tracks[0].range', 'tracks[1].range', 'tracks[2].range', 'tracks[3].range', 'tracks[4].range']
for col in track_cols:
    if col in df.columns:
        ranges = df[col].dropna()
        valid = ranges[(ranges > 0) & (ranges < 200)].tolist()
        all_ranges.extend(valid)

# Convert to numpy array
ranges = np.array(all_ranges)

# Calculate statistics
stats = {
    'min': np.min(ranges),
    'max': np.max(ranges),
    'mean': np.mean(ranges),
    'median': np.median(ranges),
    'std': np.std(ranges),
    'count': len(ranges)
}

print("=== Radar Detection Distance Analysis ===")
print(f"Total samples: {stats['count']}")
print(f"Minimum distance: {stats['min']:.2f} meters")
print(f"Maximum distance: {stats['max']:.2f} meters")
print(f"Mean distance: {stats['mean']:.2f} meters")
print(f"Median distance: {stats['median']:.2f} meters")
print(f"Standard deviation: {stats['std']:.2f} meters")

# Create visualization
plt.figure(figsize=(12, 8))

# Histogram
plt.subplot(2, 2, 1)
plt.hist(ranges, bins=15, alpha=0.7, color='blue', edgecolor='black')
plt.axvline(stats['mean'], color='red', linestyle='--', label=f'Mean: {stats["mean"]:.1f}m')
plt.xlabel('Distance (meters)')
plt.ylabel('Count')
plt.title('Radar Distance Distribution')
plt.legend()

# Box plot
plt.subplot(2, 2, 2)
plt.boxplot(ranges, vert=True)
plt.ylabel('Distance (meters)')
plt.title('Radar Distance Box Plot')

# Time series
plt.subplot(2, 2, 3)
plt.plot(ranges, alpha=0.7, color='orange')
plt.axhline(stats['mean'], color='red', linestyle='--', label='Mean')
plt.xlabel('Sample Index')
plt.ylabel('Distance (meters)')
plt.title('Radar Distance Over Time')
plt.legend()

# Statistics summary
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

Range: {stats['max'] - stats['min']:.1f} m
"""
plt.text(0.1, 0.9, text, fontsize=12, verticalalignment='top',
         bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))

plt.suptitle('Radar Detection Distance Analysis', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.savefig('radar.png', dpi=300, bbox_inches='tight')
plt.close()

print("Visualization saved as radar.png")