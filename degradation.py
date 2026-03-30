import fastf1
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

fastf1.Cache.enable_cache('cache')

session = fastf1.get_session(2024, 'Bahrain', 'R')
session.load()

drivers = ['VER', 'LEC']
colors  = {'VER': '#3671C6', 'LEC': '#E8002D'}

FUEL_EFFECT_PER_LAP = 2.3 * 0.03

fig = make_subplots(
    rows=2, cols=1,
    vertical_spacing=0.12,
    subplot_titles=[
        'Raw Lap Times — stints separated by pit stops',
        'Tyre Degradation Rate by Stint  '
        '(fuel correction: 2.3kg/lap × 0.03s/kg — estimated)'
    ]
)

summary_rows = []

for driver in drivers:
    laps = session.laps.pick_drivers(driver).copy()

    laps = laps[laps['PitOutTime'].isna()]
    laps = laps[laps['PitInTime'].isna()]
    laps = laps.dropna(subset=['LapTime', 'Compound', 'TyreLife'])

    laps['LapTimeSeconds'] = laps['LapTime'].dt.total_seconds()

    median_time = laps['LapTimeSeconds'].median()
    laps = laps[laps['LapTimeSeconds'] < median_time * 1.03]
    laps = laps[laps['LapTimeSeconds'] > median_time * 0.97]

    laps['LapNumber'] = laps['LapNumber'].astype(int)
    laps['FuelCorrectedTime'] = (laps['LapTimeSeconds']
                                  + FUEL_EFFECT_PER_LAP
                                  * (laps['LapNumber'] - 1))
    laps['Stint'] = laps['Stint'].astype(int)

    first_trace = True
    for stint_num in sorted(laps['Stint'].unique()):
        stint = laps[laps['Stint'] == stint_num].copy()
        if len(stint) < 3:
            continue

        compound  = stint['Compound'].iloc[0]
        stint_lap  = stint.sort_values('LapNumber')
        stint_tyre = stint.sort_values('TyreLife')

        show_legend = first_trace
        first_trace = False

        # Top panel — raw lap times
        fig.add_trace(go.Scatter(
            x=stint_lap['LapNumber'],
            y=stint_lap['LapTimeSeconds'],
            mode='lines+markers',
            name=driver,
            legendgroup=driver,
            showlegend=show_legend,
            line=dict(color=colors[driver], width=1.5),
            marker=dict(size=5),
            hovertemplate=(f'{driver} | Lap %{{x}}<br>'
                           f'Time: %{{y:.3f}}s<br>'
                           f'Compound: {compound}<extra></extra>')
        ), row=1, col=1)

        # Bottom panel — fuel corrected vs tyre age
        fig.add_trace(go.Scatter(
            x=stint_tyre['TyreLife'],
            y=stint_tyre['FuelCorrectedTime'],
            mode='markers',
            name=driver,
            legendgroup=driver,
            showlegend=False,
            marker=dict(color=colors[driver], size=6),
            hovertemplate=(f'{driver} | Tyre age %{{x}} laps<br>'
                           f'Corrected: %{{y:.3f}}s<br>'
                           f'Compound: {compound}<extra></extra>')
        ), row=2, col=1)

        # Degradation fit line
        if len(stint_tyre) >= 4:
            x = stint_tyre['TyreLife'].values
            y = stint_tyre['FuelCorrectedTime'].values
            coeffs   = np.polyfit(x, y, 1)
            deg_rate = coeffs[0]
            fit_fn   = np.poly1d(coeffs)
            x_line   = np.linspace(x.min(), x.max(), 100)

            fig.add_trace(go.Scatter(
                x=x_line,
                y=fit_fn(x_line),
                mode='lines',
                name=f'{driver} {compound[:4]} fit',
                legendgroup=driver,
                showlegend=False,
                line=dict(color=colors[driver], width=2, dash='dash'),
            ), row=2, col=1)

            # Annotation at end of fit line
            fig.add_annotation(
                x=x_line[-1],
                y=fit_fn(x_line[-1]),
                text=f'{driver} {compound[:4]}: {deg_rate:+.3f}s/lap',
                showarrow=True,
                arrowhead=2,
                arrowcolor=colors[driver],
                arrowwidth=1,
                ax=40, ay=-25,
                font=dict(color=colors[driver], size=10),
                bgcolor='rgba(0,0,0,0.7)',
                bordercolor=colors[driver],
                borderwidth=1,
                row=2, col=1
            )

            # Collect for summary table
            summary_rows.append({
                'Driver': driver,
                'Compound': compound,
                'Stint laps': len(stint),
                'Avg pace (s)': round(stint_tyre['LapTimeSeconds'].mean(), 3),
                'Deg rate (s/lap)': round(deg_rate, 4)
            })

# Layout
fig.update_layout(
    title=dict(
        text='Tyre Degradation Analysis — 2024 Bahrain GP Race<br>'
             '<sup>Fuel correction: 2.3kg/lap × 0.03s/kg (estimated) '
             '| Outliers filtered at ±3% of median pace</sup>',
        font=dict(size=15)
    ),
    template='plotly_dark',
    height=850,
    hovermode='x unified',
    legend=dict(orientation='h', y=-0.05)
)

fig.update_yaxes(title_text='Lap Time (s)', row=1, col=1)
fig.update_yaxes(title_text='Fuel-Corrected Lap Time (s)', row=2, col=1)
fig.update_xaxes(title_text='Lap Number', row=1, col=1)
fig.update_xaxes(title_text='Tyre Age (laps)', row=2, col=1)

# Print stint summary table to terminal
print("\n--- Stint Summary ---")
print(f"{'Driver':<8} {'Compound':<10} {'Laps':<8} "
      f"{'Avg Pace (s)':<15} {'Deg Rate (s/lap)'}")
print("-" * 55)
for row in summary_rows:
    print(f"{row['Driver']:<8} {row['Compound']:<10} "
          f"{row['Stint laps']:<8} {row['Avg pace (s)']:<15} "
          f"{row['Deg rate (s/lap)']}")

fig.write_html('degradation_analysis.html')
print("\nPlot saved — open degradation_analysis.html in your browser")
