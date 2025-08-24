#!/usr/bin/env python3
"""
Analyze radar data from CSV file and create visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def load_radar_data(csv_file):
    """Load radar data from CSV file"""
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} rows and {len(df.columns)} columns")
    return df

def extract_radar_distances(df):
    """Extract radar distance/range values from the data"""
    radar_data = []
    
    # Look for radar-related topics and columns
    radar_topics = [col for col in df.columns if 'radar' in str(col).lower()]
    print(f"Found radar-related columns: {radar_topics}")
    
    # Extract range values from different sources
    range_columns = []
    
    # Check for direct range columns
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in ['range', 'distance', 'radar']):
            if 'range' in col_lower or 'distance' in col_lower:
                range_columns.append(col)
    
    print(f"Range columns found: {range_columns}")
    
    # Extract radar range data from /radar/range topic
    radar_range_mask = df['topic'] == '/radar/range'
    if radar_range_mask.any():
        radar_range_data = df[radar_range_mask]
        if 'range' in df.columns:
            ranges = radar_range_data['range'].dropna()
            if len(ranges) > 0:
                radar_data.extend(ranges.tolist())
    
    # Extract radar tracks data
    radar_tracks_mask = df['topic'] == '/radar/tracks'
    if radar_tracks_mask.any():
        radar_tracks_data = df[radar_tracks_mask]
        
        # Extract track ranges from tracks data
        for idx, row in radar_tracks_data.iterrows():
            # Look for track range columns (tracks[0].range, tracks[1].range, etc.)
            track_cols = [col for col in df.columns if 'tracks[' in str(col) and 'range' in str(col)]
            for col in track_cols:
                if pd.notna(row[col]) and row[col] != 0:
                    radar_data.append(float(row[col]))
    
    # Extract from general range column if available
    if 'range' in df.columns:
        general_ranges = df['range'].dropna()
        if len(general_ranges) > 0:
            radar_data.extend(general_ranges.tolist())
    
    # Filter out zero/negative values and extreme outliers
    valid_ranges = [r for r in radar_data if 0 < r < 200]  # Reasonable radar range limit
    return valid_ranges

def calculate_statistics(ranges):
    """Calculate radar distance statistics"""
    if not ranges:
        return None
    
    ranges = np.array(ranges)
    stats = {
        'min': np.min(ranges),
        'max': np.max(ranges),
        'mean': np.mean(ranges),
        'median': np.median(ranges),
        'std': np.std(ranges),
        'count': len(ranges)
    }
    
    return stats

def create_visualization(ranges, stats, output_file='radar.png'):
    """Create radar distance visualization"""
    if not ranges:
        print("No valid radar data found for visualization")
        return
    
    # Set up the plotting style
    plt.style.use('default')
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Radar Detection Distance Analysis', fontsize=16, fontweight='bold')
    
    # 1. Histogram of radar distances
    ax1.hist(ranges, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
    ax1.axvline(stats['mean'], color='red', linestyle='--', linewidth=2, label=f'Mean: {stats["mean"]:.2f}m')
    ax1.axvline(stats['median'], color='green', linestyle='--', linewidth=2, label=f'Median: {stats["median"]:.2f}m')
    ax1.set_xlabel('Distance (meters)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Distribution of Radar Detection Distances')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Time series plot (if timestamp available)
    ax2.plot(ranges, alpha=0.7, color='orange', linewidth=1)
    ax2.axhline(stats['mean'], color='red', linestyle='--', linewidth=1, label='Mean')
    ax2.axhline(stats['max'], color='green', linestyle=':', linewidth=1, label=f'Max: {stats["max"]:.2f}m')
    ax2.axhline(stats['min'], color='blue', linestyle=':', linewidth=1, label=f'Min: {stats["min"]:.2f}m')
    ax2.set_xlabel('Sample Index')
    ax2.set_ylabel('Distance (meters)')
    ax2.set_title('Radar Distance Time Series')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Box plot
    ax3.boxplot(ranges, vert=True, patch_artist=True, 
                boxprops=dict(facecolor='lightblue', alpha=0.7),
                medianprops=dict(color='red', linewidth=2))
    ax3.set_ylabel('Distance (meters)')
    ax3.set_title('Radar Distance Box Plot')
    ax3.grid(True, alpha=0.3)
    
    # 4. Statistics summary
    ax4.axis('off')
    stats_text = f"""
    Radar Detection Distance Statistics
    
    Minimum:    {stats['min']:.2f} m
    Maximum:    {stats['max']:.2f} m
    Mean:       {stats['mean']:.2f} m
    Median:     {stats['median']:.2f} m
    Std Dev:    {stats['std']:.2f} m
    Samples:    {stats['count']}
    
    Data Range: {stats['max'] - stats['min']:.2f} m
    """
    ax4.text(0.1, 0.9, stats_text, fontsize=12, verticalalignment='top',
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.show()
    print(f"Visualization saved as {output_file}")

def main():
    """Main analysis function"""
    csv_file = 'df.csv'
    
    try:
        # Load data
        df = load_radar_data(csv_file)
        
        # Extract radar distances
        radar_distances = extract_radar_distances(df)
        
        if not radar_distances:
            print("No radar distance data found in the CSV file")
            return
        
        print(f"Found {len(radar_distances)} valid radar distance measurements")
        
        # Calculate statistics
        stats = calculate_statistics(radar_distances)
        
        if stats:
            print("\n=== Radar Detection Distance Statistics ===")
            print(f"Minimum Distance: {stats['min']:.2f} meters")
            print(f"Maximum Distance: {stats['max']:.2f} meters")
            print(f"Mean Distance: {stats['mean']:.2f} meters")
            print(f"Median Distance: {stats['median']:.2f} meters")
            print(f"Standard Deviation: {stats['std']:.2f} meters")
            print(f"Total Samples: {stats['count']}")
            
            # Create visualization
            create_visualization(radar_distances, stats)
        else:
            print("Unable to calculate statistics from the data")
            
    except FileNotFoundError:
        print(f"Error: File '{csv_file}' not found")
    except Exception as e:
        print(f"Error processing data: {str(e)}")

if __name__ == "__main__":
    main()