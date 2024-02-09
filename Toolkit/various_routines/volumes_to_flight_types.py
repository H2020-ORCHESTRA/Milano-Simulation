import pandas as pd
import matplotlib.pyplot as plt

plt.style.use(['science', "no-latex"])
plt.rc('font', **{'family': 'sans-serif', 'sans-serif': ['Century Gothic']})
plt.rcParams['figure.figsize'] = [25, 12]

# Remove Departures
df = pd.read_excel("volumes.xlsx")
df = df[df['*Arr/Par'] == "A"]

### Schengen Six Groups
df_Schengen = df[df['*Schengen Actual'] == "S"]

# Legacy
df_Schengen_legacy = df_Schengen[df_Schengen['GRUPPO PAX ACTUAL'] == "Legacy"]
df_Schengen_legacy_international = df_Schengen_legacy[df_Schengen_legacy['TRATTA VOLO'] == "INTERNAZIONALE"]
df_Schengen_legacy_national = df_Schengen_legacy[df_Schengen_legacy['TRATTA VOLO'] == "NAZIONALE"]

# Low Cost
df_Schengen_low_cost = df_Schengen[df_Schengen['GRUPPO PAX ACTUAL'] == "Low Cost"]
df_Schengen_low_cost_international = df_Schengen_low_cost[df_Schengen_low_cost['TRATTA VOLO'] == "INTERNAZIONALE"]
df_Schengen_low_cost_national = df_Schengen_low_cost[df_Schengen_low_cost['TRATTA VOLO'] == "NAZIONALE"]

# Leisure
df_Schengen_leisure = df_Schengen[df_Schengen['GRUPPO PAX ACTUAL'] == "Leisure"]
df_Schengen_leisure_international = df_Schengen_leisure[df_Schengen_leisure['TRATTA VOLO'] == "INTERNAZIONALE"]
df_Schengen_leisure_national = df_Schengen_leisure[df_Schengen_leisure['TRATTA VOLO'] == "NAZIONALE"]

### Non Schengen 3 groups
df_non_Schengen = df[df['*Schengen Actual'] != "S"]

# Legacy
df_Non_Schengen_legacy = df_non_Schengen[df_non_Schengen['GRUPPO PAX ACTUAL'] == "Legacy"]

# Low Cost
df_Non_Schengen_low_cost = df_non_Schengen[df_non_Schengen['GRUPPO PAX ACTUAL'] == "Low Cost"]

# Leisure
df_Non_Schengen_leisure = df_non_Schengen[df_non_Schengen['GRUPPO PAX ACTUAL'] == "Leisure"]

dataframes = [df_Schengen_legacy_international, df_Schengen_legacy_national, df_Schengen_low_cost_international,
              df_Schengen_low_cost_national, df_Schengen_leisure_international, df_Schengen_leisure_national,
              df_Non_Schengen_legacy, df_Non_Schengen_low_cost, df_Non_Schengen_leisure]

# Calculate the sum for column 'A' in each data frame
column_a_sums = [df['Pax Tot'].sum() for df in dataframes]
# Generate distinct colors for each pie slice
colors = plt.cm.Pastel1(range(len(column_a_sums)))



plt.figure(figsize=(8, 8))
pie_chart = plt.pie(column_a_sums, labels=["Schengen Legacy International", "Schengen Legacy National",
                               "Schengen Low Cost International", "Schengen Low Cost National",
                               "Schengen Leisure International", "Schengen Leisure National",
                               "Non-Schengen Legacy", "Non-Schengen Low Cost",
                               "Non-Schengen Leisure"], autopct='%1.1f%%', startangle=140,colors=colors)

# Add legend in a box to the right of the pie chart with an outline
legend = plt.legend(title='Flight Type', loc='upper left', bbox_to_anchor=(1.2, 1), fancybox=True, shadow=True, edgecolor='black')
legend.get_frame().set_linestyle('-')  # Set linestyle of the legend box outline

plt.title('Pie Chart depicting passenger percentages per Flight Type')
plt.show()
