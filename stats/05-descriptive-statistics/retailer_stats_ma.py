"""
Massachusetts Cannabis Dispensary Statistics
Copyright (c) 2021 Cannlytics and the Cannabis Data Science Meetup Group

Authors: Keegan Skeate <keegan@cannlytics.com>
Created: 11/24/2021
Updated: 11/24/2021
License: MIT License <https://opensource.org/licenses/MIT>

Objective:
    
    Calculate the following statistics in Massachusetts:
        - Retailers per 100,000 adults
        - Revenue per retailer
    
Data Sources:
    
    MA Cannabis Control Commission
    - Approved Massachusetts Licensees: https://dev.socrata.com/foundry/opendata.mass-cannabis-control.com/hmwt-yiqy
    - Plant Activity and Volume: https://dev.socrata.com/foundry/opendata.mass-cannabis-control.com/j3q7-3usu
"""
from dotenv import dotenv_values
import matplotlib.pyplot as plt
import pandas as pd
import requests

# Internal imports
from utils import (
    end_of_period_timeseries,
    reverse_dataframe,
)

#--------------------------------------------------------------------------
# Get MA public cannabis data.
#--------------------------------------------------------------------------

# Setup Socrata API, setting the App Token for request headers.
config = dotenv_values('../.env')
app_token = config.get('APP_TOKEN', None)
headers = {'X-App-Token': app_token}
base = 'https://opendata.mass-cannabis-control.com/resource'

# Get licensees data.
url = f'{base}/hmwt-yiqy.json'
params = {'$limit': 10000,  '$order': 'app_create_date DESC'}
response = requests.get(url,  headers=headers, params=params)
licensees = pd.DataFrame(response.json(), dtype=float)

# Get production stats (total employees, total plants, etc.) j3q7-3usu
url = f'{base}/j3q7-3usu.json'
params = {'$limit': 2000, '$order': 'activitysummarydate DESC'}
response = requests.get(url,  headers=headers, params=params)
production = pd.DataFrame(response.json(), dtype=float)
production = reverse_dataframe(production)
production['date'] = pd.to_datetime(production['activitysummarydate'])
production.set_index('date', inplace=True)

# Calculate sales difference, coding outliers and negatives as 0.
production['sales'] = production['salestotal'].diff()
outlier = production.loc[production.sales >= 10000000]
production.at[outlier.index, 'sales'] = 0
negatives = production.loc[production.sales < 0]
production.at[negatives.index, 'sales'] = 0

#--------------------------------------------------------------------------
# Re-look at weekly averages using only licensees with final licenses.
#--------------------------------------------------------------------------

# Identify licensees with final licenses.
# These are the licenses that are assumed to be currently operating.
final_licensees = licensees.loc[
    (licensees['approved_license_type'] == 'FINAL LICENSE')
]

# Create weekly series.
weekly_sales = production.sales.resample('W-SUN').sum()
weekly_plants = production['total_plantfloweringcount'].resample('W-SUN').mean()
weekly_employees = production.total_employees.resample('W-SUN').mean()

# Create total licensees series.
production['total_retailers'] = 0
production['total_cultivators'] = 0
production['total_licensees'] = 0
for index, _ in production.iterrows():
    timestamp = index.isoformat()
    production.at[index, 'total_retailers'] = len(licensees.loc[
        (licensees.license_type == 'Marijuana Retailer') &
        (licensees['cnb_dt_of_final_licensure'] <= timestamp)
    ])
    production.at[index, 'total_cultivators'] = len(licensees.loc[
        (licensees.license_type == 'Marijuana Cultivator') &
        (licensees['cnb_dt_of_final_licensure'] <= timestamp)
    ])
    production.at[index, 'total_licensees'] = len(licensees.loc[
        (licensees['cnb_dt_of_final_licensure'] <= timestamp)
    ])

# Create weekly averages.
weekly_total_retailers = production['total_retailers'].resample('W-SUN').mean()
weekly_total_cultivators = production['total_cultivators'].resample('W-SUN').mean()
weekly_total_licensees = production['total_licensees'].resample('W-SUN').mean()

# Estimate sales per retailer.
sales_per_retailer = weekly_sales / weekly_total_retailers
(sales_per_retailer / 1000).plot()
plt.show()

# Estimate plants per cultivator.
plants_per_cultivator = weekly_plants / weekly_total_cultivators
plants_per_cultivator.plot()
plt.show()

# Estimate employees per licensee.
employees_per_license = weekly_employees / weekly_total_licensees
employees_per_license.plot()
plt.show()

# Calculate sales per retailer in 2020.
avg_2020_sales = sales_per_retailer.loc[
    (sales_per_retailer.index >= pd.to_datetime('2020-01-01')) &
    (sales_per_retailer.index < pd.to_datetime('2021-01-01'))
].sum()
print('Sales per retailer in MA in 2020: %.2fM' % (avg_2020_sales / 1_000_000))

#--------------------------------------------------------------------------
# Calculate retailers per population.
#--------------------------------------------------------------------------
from fredapi import Fred

# Initialize FRED API client.
fred_api_key = config.get('FRED_API_KEY')
fred = Fred(api_key=fred_api_key)

# Get MA population (conjecturing that population remains constant in 2021).
observation_start = production.index.min().isoformat()
population = fred.get_series('MAPOP', observation_start=observation_start)
population = end_of_period_timeseries(population, 'Y')
population = population.multiply(1000) # thousands of people
new_row = pd.DataFrame([population[-1]], index=[pd.to_datetime('2021-12-31')])
population = pd.concat([population, pd.DataFrame(new_row)], ignore_index=False)

# Calculate retailers per population.
weekly_population = population[0].resample('W-SUN').mean().pad()
retailers_per_capita = weekly_total_retailers / (weekly_population / 100_000)
retailers_per_capita.plot()

# Calculate retailers per capita in 2020.
avg_retailers_per_capita_2020 = retailers_per_capita.loc[
    (retailers_per_capita.index >= pd.to_datetime('2020-01-01')) &
    (retailers_per_capita.index < pd.to_datetime('2021-01-01'))
].mean()
print('Retailers per capita in MA in 2020: %.2f' % avg_retailers_per_capita_2020)

#--------------------------------------------------------------------------
# Estimate the relationship between dispensaries per capita and
# sales per dispensary.
#--------------------------------------------------------------------------

# # Read in retailer statistics (from Nevada's technical memorandum).
# retailer_stats = pd.read_excel('./data/retailer_stats.xlsx')

# # Look at only observations with revenue per retailer.
# stats = retailer_stats[~retailer_stats['revenue_per_retailer'].isnull()]

# # Run a regression of sales per retailer on retailers per 100,000 adults.
# Y = stats['revenue_per_retailer']
# X = stats['retailers_per_100_000']
# X = sm.add_constant(X)
# regression = sm.OLS(Y, X).fit()
# print(regression.summary())

# # Interpret the relationship.
# beta = regression.params.values[1]
# statement = """If retailers per 100,000 adults increases by 1,
# then everything else held constant one would expect
# revenue per retailer to change by {}.
# """.format(format_thousands(beta))
# print(statement)

# # Visualize the regression.
# ax = stats.plot(
#     x='retailers_per_100_000',
#     y='revenue_per_retailer',
#     kind='scatter'
# )
# abline_plot(
#     model_results=regression,
#     ax=ax
# )
# plt.show()

