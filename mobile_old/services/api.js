/**
 * FraudSentinel Mobile - API Service
 * Centralized fetch handler for backend communication.
 */

// In a real Expo app, use Constants.expoConfig.extra.apiUrl or process.env.EXPO_PUBLIC_API_URL
const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export const api = {
  async fetchHealth() {
    const response = await fetch(`${BASE_URL}/health`);
    return response.json();
  },

  async fetchHistory(limit = 20) {
    const response = await fetch(`${BASE_URL}/history?limit=${limit}`);
    return response.json();
  },

  async fetchAlerts(limit = 20) {
    const response = await fetch(`${BASE_URL}/alerts?limit=${limit}`);
    return response.json();
  },

  async chatPredict(message) {
    const response = await fetch(`${BASE_URL}/chat_predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return response.json();
  }
};
