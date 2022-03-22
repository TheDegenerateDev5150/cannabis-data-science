"""
Brand Analysis
Copyright (c) 2022 Cannlytics

Authors: Keegan Skeate <keegan@cannlytics.com>
Created: 3/21/2022
Updated: 3/21/2022
License: MIT License <https://opensource.org/licenses/MIT>

Description: This script performs brand analysis of the top cannabis-infused
beverage brands in Washington State using cannabis traceability data.

Data sources:

    - WA State Traceability Data January 2018 - November 2021
    https://lcb.app.box.com/s/e89t59s0yb558tjoncjsid710oirqbgd

    - Random Sample of WA Sales Items from 2022-03-16
    https://cannlytics.page.link/cds57

"""
# Standard imports.
from calendar import monthrange

# External imports.
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import statsmodels.api as sm

# Define the plot style.
plt.style.use('fivethirtyeight')
plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 24})


#--------------------------------------------------------------------------
# Read the sample sales data.
# Random sample of sales: https://cannlytics.page.link/cds57
#--------------------------------------------------------------------------

# Read in the data from where your data lives.
DATA_DIR = '../.datasets'
DATA_FILE = f'{DATA_DIR}/random-sales-items-2022-03-16.csv'
data = pd.read_csv(DATA_FILE, low_memory=False, parse_dates=['date'], index_col=0)

# Restrict the time period.
data = data.loc[
    (data['date'] >= pd.to_datetime('2020-01-01')) &
    (data['date'] < pd.to_datetime('2021-11-01'))
]

# Remove sale outliers.
data = data.loc[data['price_total'] >= 0.25]

# Optional: Read licensees data for quick cross-referencing.
licensees = pd.read_csv(
    f'{DATA_DIR}/augmented-washington-state-licensees/augmented-washington-state-licensees.csv',
    index_col=0,
    low_memory=False,
)

#--------------------------------------------------------------------------
# Organize the data.
#--------------------------------------------------------------------------

# Identify product type data.
flower_data = data.loc[data['intermediate_type'] == 'usable_marijuana']
concentrate_data = data.loc[data['intermediate_type'] == 'concentrate_for_inhalation']
edible_data = data.loc[data['intermediate_type'] == 'solid_edible']
beverage_data = data.loc[(data['intermediate_type'] == 'liquid_edible')]
preroll_data = data.loc[data['intermediate_type'] == 'infused_mix']

# Find all businesses that operated.
retailers = [i for i in list(data['mme_id'].unique()) if pd.notna(i)]
cultivators = [i for i in list(flower_data['producer_mme_id'].unique()) if pd.notna(i)]
processors = [i for i in list(concentrate_data['producer_mme_id'].unique()) if pd.notna(i)]
manufacturers = [i for i in list(edible_data['producer_mme_id'].unique()) if pd.notna(i)]
beverages = [i for i in list(beverage_data['producer_mme_id'].unique()) if pd.notna(i)]
prerollers = [i for i in list(preroll_data['producer_mme_id'].unique()) if pd.notna(i)]

# Create time series data.
variables = {
    'price_total': ['mean', sum, 'count'],
    'price_per_mg_thc': ['mean'],
    'cannabinoid_d9_thca_percent': ['mean',],
    'total_cannabinoid_percent': ['mean',],
    'weight': ['mean', sum],
    'mme_id': 'nunique',
}
cultivator_panel = flower_data.groupby(['producer_mme_id', pd.Grouper(key='date', freq='M')]).agg(variables)
processor_panel = concentrate_data.groupby(['producer_mme_id', pd.Grouper(key='date', freq='M')]).agg(variables)
manufacturer_panel = edible_data.groupby(['producer_mme_id', pd.Grouper(key='date', freq='M')]).agg(variables)
beverages_panel = beverage_data.groupby(['producer_mme_id', pd.Grouper(key='date', freq='M')]).agg(variables)
preroller_panel = preroll_data.groupby(['producer_mme_id', pd.Grouper(key='date', freq='M')]).agg(variables)


#--------------------------------------------------------------------------
# Modelling beverage brands.
#--------------------------------------------------------------------------

# Specify the product category of interest.
product_data = beverage_data

# Create monthly panel data.
group = ['producer_mme_id', pd.Grouper(key='date', freq='M')]
beverage_panel = product_data.groupby(group, as_index=False).agg(variables)


#--------------------------------------------------------------------------
# Estimate market share (percent) for the top brands in each category.
#--------------------------------------------------------------------------

# Estimate total sales by producer.
producer_sales = product_data.groupby('producer_mme_id')['price_total'].sum()

# Identify the top 5 producers.
top_beverage_producers = producer_sales.nlargest(5)

# Estimate the total amount of beverage sales (in thousands of $).
total_sales = producer_sales.sum()

# Calculate the market shares and concentration ratio (CR5).
# Note: As a rule of thumb, when using n=5 anything over 0.6 or 60% is
# considered an oligopoly, whereas anything under 0.5 or 50% can be
# considered competitive and lowly concentrated.
concentration_ratio = 0
market_shares = {}
for mme_id, group in top_beverage_producers.iteritems():
    name = data.loc[data['producer_mme_id'] == mme_id].iloc[0]['producer_name']
    market_share = group / total_sales
    market_shares[name.title()] = market_share * 100
    concentration_ratio += market_share

market_share_data = pd.DataFrame([market_shares], index=['Market Share']).T
print(market_share_data)
print('Concentration ratio: %.2f' % concentration_ratio)

# Visualize the data.
market_share_data.loc['Everyone Else'] = 100 - market_share_data['Market Share'][:5].sum()
plt.figure(figsize=(16, 12))
ax1 = plt.subplot(121, aspect='equal')
market_share_data.plot(
    kind='pie',
    y='Market Share',
    ax=ax1,
    autopct='%1.1f%%', 
    startangle=180,
    shadow=False,
    legend = False,
    fontsize=14,
    colors=sns.husl_palette(10, h=0.0, s=0.8, l=0.725),
    wedgeprops = {'linewidth': 1, 'edgecolor': '#fff'}
)
plt.title('Market Share of the Top 5 Beverage Producers in Washington', fontsize=24)
plt.show()

# Calculate market share for all beverage producers.
market_shares = product_data.groupby('producer_mme_id')['price_total'].sum().apply(
    lambda x: round(x / total_sales * 100, 2)
)
market_shares = market_shares.sort_values(ascending=False)
for mme_id, value in market_shares[:5].iteritems():
    name = data.loc[data['producer_mme_id'] == mme_id].iloc[0]['producer_name']
    print(name.title(), round(value, 2))


def calculate_market_share(series):
    """Calculate market share for a vendor given the date."""
    date = series.name[1]
    sales = data.loc[data['date'].dt.date == date]['price_total'].sum()
    return round(series['price_total'].sum() / sales * 100, 2)

# Estimate monthly market shares.
group = ['producer_mme_id', pd.Grouper(key='date', freq='M')]
monthly_market_shares = product_data.groupby(group).apply(calculate_market_share)
print(monthly_market_shares)


#--------------------------------------------------------------------------
# Estimate market penetration rate (percent).
#--------------------------------------------------------------------------

def calculate_penetration_rate(series, n):
    """Calculate retailer penetration for a distributor."""
    return round(len(series.unique()) / n * 100, 2)


# Calculate overall penetration rates.
penetration_rates = product_data.groupby('producer_mme_id')['mme_id'].apply(
    lambda x: calculate_penetration_rate(x, len(retailers))
)
penetration_rates = penetration_rates.sort_values(ascending=False)
for mme_id, value in penetration_rates[:5].iteritems():
    name = data.loc[data['producer_mme_id'] == mme_id].iloc[0]['producer_name']
    print(name.title(), value)

# Calculate monthly penetration rates.
monthly_penetration_rates = product_data.groupby(group)['mme_id'].apply(
    # FIXME: Use count of retailers that bought that product in that month.
    lambda x: calculate_penetration_rate(x, len(retailers))
)


#--------------------------------------------------------------------------
# Estimate the average purchase frequency (APF).
# The average number of items bought by retailers who bought a vendor's
# products in a given month.
#--------------------------------------------------------------------------

def calculate_average_purchase_frequency(series):
    """Calculate the average number of items by retailer for given vendor and time."""
    items_per_retailer = series.groupby('mme_id')['price_total'].count()
    return round(items_per_retailer.mean(), 4)

# Estimate average purchase frequency.
group = ['producer_mme_id', pd.Grouper(key='date', freq='M')]
apf = product_data.groupby(group).apply(calculate_average_purchase_frequency)
print(apf * 1000)

# Look at a specific date.
apf.loc[apf == apf.max()]
pf = product_data.groupby(group + ['mme_id'])['price_total'].count()
pf.loc['WAWA1.MME3', '2021-04-30'].describe()
pf.loc['WAWA1.MM1FV', '2021-08-31'].describe()

# Estimate the average time between purchases (TBP) (1 mo / APF).
tbps = []
for index, value in apf.iteritems():
    date =  index[1]
    days = monthrange(date.year, date.month)[1]
    tbps.append(days / value)
monthly_tbp = pd.Series(tbps, index=apf.index)

# Look at highest frequency of sales.
for index, value in monthly_tbp.nsmallest(10).iteritems():
    mme_id = index[0]
    name = data.loc[data['producer_mme_id'] == mme_id].iloc[0]['producer_name']
    print(name.title(), value)


#--------------------------------------------------------------------------
# Estimate the repeat purchase rate (RPR).
# The percentage of current product retailers that purchase more than once.
#--------------------------------------------------------------------------

def find_repeating(lst):
    """Find all unique elements that are repeated in a list.
    Credit: BitBeats <https://codereview.stackexchange.com/a/200285>
    License: CC BY-SA 4.0 <https://creativecommons.org/licenses/by-sa/4.0/>
    """
    duplicates = []
    lst.sort()
    for i in range(len(lst) - 1):
       if lst[i] == lst[i + 1]:
          duplicates.append(lst[i])
    return set(duplicates)


def calculate_repeat_purchase_rate(series):
    """Calculate the repeat purchase rate for a vendor in a time period."""
    total = series.nunique()
    consumer_count = len(find_repeating(list(series)))
    return round(consumer_count / total * 100, 2)


# Estimate the repeat purchase rate (RPR).
group = ['producer_mme_id', pd.Grouper(key='date', freq='M')]
monthly_rpr = product_data.groupby(group)['mme_id'].apply(calculate_repeat_purchase_rate)
print(monthly_rpr)


#--------------------------------------------------------------------------
# Optional: Are there any brands that are only sold at 1 retail location?
#--------------------------------------------------------------------------



#--------------------------------------------------------------------------
# Estimate the numbers of purchases of a brand of consumer goods.
#--------------------------------------------------------------------------

# Estimate number of purchases by month.
purchases = product_data.groupby(group)['price_total'].count()
monthly_purchases = product_data.groupby(group, as_index=False)['price_total'].count()

# Look at the distribution of purchases for the top 5 producers (by market share).
top_purchases = monthly_purchases.loc[
    monthly_purchases['producer_mme_id'].isin(top_beverage_producers.index)
]
top_purchases = pd.merge(
    left=top_purchases,
    right=licensees[['global_id', 'name']],
    how='left',
    left_on='producer_mme_id',
    right_on='global_id'
)

# Plot the density of number of beverages sold by month for top producers.
# Note: This assumes a normal distribution
plt.figure(figsize=(16, 12))
sns.kdeplot(data=top_purchases, x='price_total', hue='name')
plt.xlabel('Monthly Number of Beverages Sold')
plt.xlim(0)
plt.show()

# Try to fit a negative binomial distribution!
import numpy as np
from scipy.stats import nbinom

i = 0
colors = sns.color_palette('Set1')
fig, ax = plt.subplots(figsize=(15, 8))
for index, value in top_purchases.groupby('producer_mme_id'):

    # Get a color.
    color = colors[i]
    i += 1

    # Fit a negative binomial distribution.
    s = value['price_total'] * 1000
    X = np.ones_like(s)
    res = sm.NegativeBinomial(s, X).fit(start_params=[1, 1])
    mu = np.exp(res.params[0])
    p = 1 / (1 + np.exp(res.params[0]) * res.params[1])
    n = np.exp(res.params[0]) * p / (1 - p)

    # Plot the fitted distribution with the data.
    name = value['name'].iloc[0].title()
    x_plot = np.linspace(0, 100, 101)
    ax = sns.distplot(s, color=color, bins=20)
    ax.plot(x_plot, nbinom.pmf(x_plot, n, p), lw=2, label=name, color=color)

# Format the plot.
leg = ax.legend(fontsize=18)
plt.xlim(0)
plt.xlabel('Beverages Sold per Month')
plt.title('Negative Binomial Distribution Fitted to Beverage Sales')
plt.show()


#--------------------------------------------------------------------------
# TODO: Estimate customer lifetime value for each vendor.
# The number of transactions (T) multiplied by the average order value (AOV)
# multiplied by the average retention rate (R), multiplied by the
# average gross margin (AGM).
#--------------------------------------------------------------------------

# TODO: Estimate the average number of transactions (T) per retailer by vendor.
transactions = None


# TODO: Estimate average order value (AOV).
aov = None


# TODO: Estimate the average retention rate (R).
retention_rate = None


# TODO: Estimate the average gross margin (AGM).
agm = 0.15


# TODO: Finally, estimate customer lifetime value by vendor (LV = T x AOV x R x AGM).
customer_lifetime_value = transactions * aov * retention_rate * agm


# TODO: Question: How much commission should each vendor pay their marketers for
# a customer (retailer) acquisition?
commission_rates = [0.05, 0.15, 0.25, 0.45]


#--------------------------------------------------------------------------
# Begin analyzing key performance indicators and their correlation.
#--------------------------------------------------------------------------

# Aggregate the fields for analysis.
datasets = {
    'market_share': monthly_market_shares,
    'penetration_rate': monthly_penetration_rates,
    'repeat_purchase_rate': monthly_rpr,
    'avg_purchase_frequency': apf,
    'avg_time_between_purchases': monthly_tbp,
    'purchases': purchases,
}
sample = pd.concat(datasets.values(), axis=1)
sample.columns = datasets.keys()

# Begin to look at correlation.
fig, ax = plt.subplots(figsize=(15, 8))
sns.heatmap(sample.corr(), annot=True, square=True)
plt.yticks(rotation=0)
plt.show()

# Estimate a regression of market share on penetration rate.
Y = sample['market_share']
X = sample['penetration_rate']
X = sm.add_constant(X)
regression = sm.OLS(Y, X).fit()
print(regression.summary())

# Visualize the regression results.
fig, ax = plt.subplots(figsize=(15, 8))
sns.regplot(
    y='market_share',
    x='repeat_purchase_rate',
    data=sample,
    ci=99,
    robust=True,
    scatter_kws={'s': 200},
)
plt.show()


#--------------------------------------------------------------------------
# Correlate key performance indicators (KPIs) with Census data.
#
# Attribution: This product uses the Census Bureau Data API but
# is not endorsed or certified by the Census Bureau.
#
# API Key: https://api.census.gov/data/key_signup.html
#
# Desired Census data points to explore:
# - Crime per retail county
# - Median income per county
# - Number of tourists / travelers by county?
# - Weather
# - Birth rates
# - Education levels
#--------------------------------------------------------------------------

# Augment with producer's data. (necessary?)
# product_data = pd.merge(
#     left=product_data,
#     right=licensees[['global_id', 'name', 'county']],
#     how='left',
#     left_on='producer_mme_id',
#     right_on='global_id'
# )


# TODO: Get Census Data


# from dotenv import dotenv_values
# from census import Census # pip install census
# from us import states # pip install us
# import requests

# # Create a request session.
# session = requests.session()
# session.headers.update({'User-Agent': 'census-demo/0.0'})

# # Read your Census API key.
# config = dotenv_values('../.env')
# census_api_key = api_key=config['CENSUS_API_KEY']

# # Make requests to the Census API.
# client = Census(census_api_key, session=session)
# census_data = client.acs5.get(
#     ('NAME', 'B25034_010E'),
#     {'for': 'state:{}'.format(states.MD.fips)}
# )

# # Examples:
# # c.acs5.get('B01001_004E', {'for': 'state:*'})
# # c.acs5.state('B01001_004E', Census.ALL)
# # c.sf1.state_county_tract('NAME', states.AK.fips, '170', Census.ALL)

# Optional: Calculate avg. monthly consumption per capita.


# TODO: Regress various brand metrics on various explanatory factors.


# How does number of sales relate to county-level factors?


# How does sales relate to county-level factors?


# How does market penetration relate to county-level factors?




#--------------------------------------------------------------------------
# For Saturday Morning Statistics:
# Use an ordered probit to predict the brand rank given various factors.
#--------------------------------------------------------------------------

# Optional: Use a Chi square test to determine the most appropriate model.


#--------------------------------------------------------------------------
# Next week: Analyze seasonality statistics.
#--------------------------------------------------------------------------

# Calculate relative sales over time.


# Estimate trends.


# Estimate day of the week effects.


# Estimate seasonal effects.


# Estimate day of the year effects.
# New Year
# Valentine's Day
# Leap Day
# April 20th (Chronukkah)
# Memorial Day
# July 4th (Independence Day)
# Labor Day
# Halloween
# Thanksgiving
# Christmas

# days_of_interest = {
#     'New Year': [pd.to_datetime('2020-01-01'), pd.to_datetime('2021-01-01')],
#     "Valentine's Day": [pd.to_datetime('2020-01-01'), pd.to_datetime('2021-01-01')],
# }
# from pandas.tseries.holiday import USFederalHolidayCalendar
# cal = USFederalHolidayCalendar()
# holidays = cal.holidays(start='2014-01-01', end='2014-12-31').to_pydatetime()
# if datetime.datetime(2014,01,01) in holidays:
#     print True

