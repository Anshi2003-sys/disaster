def predict_disaster(rainfall, temperature, humidity):
    
    if rainfall > 200:
        return "High Flood Risk"
    
    elif temperature > 40 and humidity < 30:
        return "High Fire Risk"
    
    elif rainfall > 150 and humidity > 80:
        return "Landslide Risk"
    
    else:
        return "Low Risk"