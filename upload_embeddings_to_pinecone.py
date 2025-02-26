

from google.colab import files
uploaded = files.upload()

# Install Pinecone client (if not already installed)
!pip install -U pinecone-client

# Import and initialize Pinecone
from pinecone import Pinecone, ServerlessSpec



# Initialize the Pinecone instance
pc = Pinecone(api_key=api_key)

# Retrieve and print the list of indexes
indexes = pc.list_indexes().names()
print("Indexes in the environment:")
for index in indexes:
    print(index)

!pip install openai==0.28

import openai
import pandas as pd
import numpy as np
from pinecone import Pinecone, ServerlessSpec

index_name = "promo-roi-file"

pc.create_index(
    name=index_name,
    dimension=1536, # Replace with your model dimensions
    metric="cosine", # Replace with your model metric
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    )
)

# Connect to the index
index = pc.Index(index_name)

"""# **Define key functions & parameters**"""

variables_explanation = """
    Below are the definitions of key business terms and variables:

    1. **List_Price**: The price at which an item is sold to the retailer or customer by the manufacturer.
    2. **Customer**: The name of the customer, retailer, or banner.
    3. **Week_Type**: Indicates whether the week is a promotion week or a non-promotion week.
    4. **Merch**: The method or vehicle used to execute the promotion (e.g., ISF_&_Flyer, ISF_Only, ISF_&_Ad).
    5. **Base_Units**: The number of units sold during a non-promotion week.
    6. **Item**: The name of the item sold by the manufacturer to the retailer and subsequently to the consumer.
    7. **Base_Price**: The selling price of an item in a non-promotion week.
    8. **Promo_Price**: The selling price of an item during a promotion week.
    9. **Price**: The price of an item during a given week. Equal to Base_Price if the item is not on promotion, or Promo_Price if it is.
    10.**Base_Retailer_Margin_Unit**: The retailer margin per unit during a non-promotion week. It is calculated as (Base_Price - List_Price + EDLP_Trade_Unit).
    11. **Promo_Units**: The number of units sold during a promotion week.
    12. **Units**: The total number of units sold during a given week (Base_Units if no promotion, Promo_Units if on promotion).
    13. **Predicted_Units**: The number of units predicted by the model for a given week.
    16. **COGS_Unit**: The cost to produce or manufacture the item.
    17. **Margin_%**: The retailer margin percentage, calculated as (Price - List_Price + Trade_Unit) / Price.
    19. **Base_Retailer_Margin_Unit**: The retailer margin per unit during a non-promotion week, calculated as (Base_Price - List_Price + EDLP_Trade_Unit) / Base_Price. This equal to Margin_% if the week is a non-promotion week.
    20. **Min_Margin_%**: The minimum retail margin required each week.
    21. **EDLP_Trade_Unit**: The allowance per unit given to the customer or retailer when the item is not on promotion.
    22. **Var_Trade_Unit**: Additional allowance per unit given during a promotion week.
    23. **Trade_Unit**: The total amount paid back to the retailer or customer to achieve the desired retail selling price.
    24. **Trade_Rate**: Defined as Trade_Unit / List_Price.
    25. **Profit_Unit**: The net profit on the item after all costs and allowances.
    26. **%_Profit_Unit**: The percentage of profit per unit, calculated as Profit_Unit / List_Price.
    27. **Lift_%**: The increase in unit volume during promotion vs. non-promotion periods, calculated as (Promo_Units - Base_Units) / Base_Units.
    28. **Inc_Profit**: Incremental profit when sold on promotion vs. no promotion.
    29. **ROI**: Return on investment from running a promotion in a given week, calculated as Inc_Profit / (Promo_Units * Var_Trade_Unit).
    31. **Discount**: The dollar discount offered during a promotion, calculated as (Base_Price - Promo_Price).
    32. **Predicted_Sales**: The dollar sales of an item sold during a week, calculated as Predicted_Units * Price.
    33. **Predicted_Base_Sales**: The predicted dollar sales assuming the week was a non-promotion week.
    """

formula_functions = {
        "Margin_%": "lambda Base_Price, Promo_Price, List_Price, EDLP_Trade_Unit, Var_Trade_Unit, Week_Type: "
                    "(Base_Price - List_Price + EDLP_Trade_Unit) / Base_Price if Week_Type == 'Base' else "
                    "(Promo_Price - List_Price + EDLP_Trade_Unit + Var_Trade_Unit) / Promo_Price",

        "Trade_Unit": "lambda EDLP_Trade_Unit, Var_Trade_Unit, Week_Type: "
                      "EDLP_Trade_Unit if Week_Type == 'Base' else EDLP_Trade_Unit + Var_Trade_Unit",

        "Trade_Rate": "lambda Trade_Unit, List_Price: Trade_Unit / List_Price",

        "Profit_Unit": "lambda List_Price, COGS_Unit, EDLP_Trade_Unit, Var_Trade_Unit, Week_Type: "
                      "List_Price - COGS_Unit - EDLP_Trade_Unit if Week_Type == 'Base' else "
                      "List_Price - COGS_Unit - (EDLP_Trade_Unit + Var_Trade_Unit)",

        "Profit_Unit_Percentage": "lambda Profit_Unit, List_Price: Profit_Unit / List_Price",

        "Lift_%": "lambda Promo_Units, Base_Units: (Promo_Units - Base_Units) / Base_Units if Week_Type == 'Base' else 0",

        "Inc_Profit": "lambda Promo_Units, Base_Units, List_Price, COGS_Unit, EDLP_Trade_Unit, Var_Trade_Unit: "
                      "(Promo_Units * (List_Price - COGS_Unit - EDLP_Trade_Unit - Var_Trade_Unit)) - "
                      "(Base_Units * (List_Price - COGS_Unit - EDLP_Trade_Unit)) if Promo_Units > 0 else 0",

        "ROI": "lambda Inc_Profit, Var_Trade_Unit, Promo_Units: Inc_Profit / (Promo_Units * Var_Trade_Unit) "
              "if Var_Trade_Unit > 0 else 0",

        "Discount": "lambda Base_Price, Promo_Price: (Base_Price - Promo_Price) / Base_Price * 100 if Base_Price > 0 else 0"
      }

available_formulas = {
        "Discount": ["discount", "price discount", "percentage off", "discounted price"],
        "Customer": ["customer", "retailer", "store, banner"],
        "Week_Type": ["week type", "promotion week", "non-promotion week"],
        "Merch": ["merch", "promotion method", "promotion type, Merchandizing", "Merchandizing strategy"],
        "Item": ["item", "product", "product name"],
        "Lift_%": ["unit lift", "percentage lift", "lift in units", "% lift", "sales lift"],
        "Margin_%": ["margin", "retailer margin", "retail margin", "customer margin"],
        "Min_Margin_%": ["min margin", "minimum margin", "minimum retail margin"],
        "Trade_Unit": ["trade per unit", "allowance per unit", "total allowance", "trade allowance"],
        "Trade_Rate": ["trade rate", "rate of trade", "% trade investment"],
        "Profit_Unit": ["profit per unit", "unit profit", "profit per item"],
        "%_Profit_Unit": ["profit percentage", "unit profit percentage", "% profit per unit"],
        "Inc_Profit": ["incremental profit", "added profit", "promo profit", "incremental sales profit"],
        "%_ROI": ["roi", "return on investment", "promo roi", "return on trade investment"],
        "Base_Retailer_Margin_Unit": ["base retailer margin per unit", "base retailer margin per item"],
        "Retailer_Margin_Unit": ["retailer margin per unit", "retailer margin per item"],
        "Predicted_Units": ["Units", "Total Units"],
        "Predicted_Base_Units": ["Base Units, Total Base Units"],
        "Predicted_Base_Sales": ["Base Sales, Total Base Sales, Dollar Base Sales"],
        "Predicted_Sales": ["Sales, Total Sales, Dollar Sales"]
        }

def fetch_stored_data():
    """
    Fetches and returns the stored variables_explanation, formula_functions, and available_formulas
    from Pinecone.
    """
    keys = ["variables_explanation", "formula_functions", "available_formulas"]
    stored_data = {}

    # Fetch the stored data directly by keys
    pinecone_response = index.fetch(ids=keys)

    # Check if data exists and retrieve it, otherwise set None
    for key in keys:
        if key in pinecone_response['vectors']:
            stored_data[key] = pinecone_response['vectors'][key]['metadata']['text']
        else:
            print(f"Debug: {key} not found in Pinecone.")
            stored_data[key] = None  # If no data found for a key, set it to None

    # Ensure that the function returns values in the correct order
    return stored_data.get('variables_explanation'), stored_data.get('formula_functions'), stored_data.get('available_formulas')

def explain_variables_to_gpt(variables_explanation, formula_functions, available_formulas):

    # Send the explanation to GPT-4
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an assistant that understands business terminologies for determining promotions effectiveness."},
            {"role": "user", "content": f"Variables Explanation: {variables_explanation}\nFormula Functions: {formula_functions}\nAvailable Formulas: {available_formulas}"}
        ],
        max_tokens=500
    )

    # Return the response from GPT-4
    return variables_explanation, formula_functions, available_formulas, response['choices'][0]['message']['content']

# Example usage
variables_explanation, formula_functions, available_formulas, gpt_response = explain_variables_to_gpt(variables_explanation, formula_functions, available_formulas)
print("GPT-4 Response:\n", gpt_response)

"""# **Store & Fetch Formulas, Variable Explanations as embeddings in Pinecone**"""

# Utility function to create embeddings
def create_embedding(text):
    return openai.Embedding.create(input=text, model="text-embedding-ada-002")['data'][0]['embedding']

file = "promo_data_spark"

# Function to store dataset in Pinecone
def store_dataset_in_pinecone(file):
    """
    Loads dataset from an Excel file, creates embeddings for each row based on relevant columns,
    and stores them in Pinecone.
    """
    # Load the dataset
    trade_strategy_combinations = pd.read_csv(file)

    # Define relevant columns
    relevant_columns = [
        'Base_Price', 'Price', 'Discount', 'Customer', 'Item', 'Week_Type',
        'Promo_Type', 'Merch', 'List_Price', 'COGS_Unit', 'Margin_%',
        'Base_Retailer_Margin_Unit', 'EDLP_Trade_Unit', 'Retailer_Margin_Unit',
        'Var_Trade_$_Unit', 'Trade_Unit', 'Trade_Rate', 'Profit_Unit',
        'Profit_Unit_Percentage', 'Predicted_Units', 'Base_Units', 'Lift_%',
        'Predicted_Sales', 'Predicted_Base_Sales', 'Inc_Profit', 'ROI'
    ]

    # Upsert each row to Pinecone
    for idx, row in trade_strategy_combinations.iterrows():
        # Create a descriptive text for each row based on relevant columns
        row_text = ' '.join([f"{col}: {row[col]}" for col in relevant_columns if pd.notnull(row[col])])

        # Create embedding for the row text
        embedding = openai.Embedding.create(input=row_text, model="text-embedding-ada-002")['data'][0]['embedding']

        # Upsert the row to Pinecone with a unique ID (use idx as the ID)
        index.upsert([(str(idx), embedding, {'text': row_text})])

    print("Dataset has been stored in Pinecone.")

# Call the function to store the dataset in Pinecone
store_dataset_in_pinecone('promo_data_spark.csv')
