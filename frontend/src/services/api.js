import axios from "axios";

const API_BASE_URL = "http://localhost:7000";

export const getInventory = async () => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/inventory`);
    return res.data;
  } catch (err) {
    console.error("Failed to fetch inventory:", err);
    return [];
  }
};

export const getOrders = async () => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/orders`);
    return res.data;
  } catch (err) {
    console.error("Failed to fetch orders:", err);
    return [];
  }
};

export const getAnalytics = async () => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/db-analytics`);
    return res.data;
  } catch (err) {
    console.error("Failed to fetch analytics:", err);
    return {};
  }
};

export const approvePO = async (poId) => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/po/${poId}/approve`);
    return res.data;
  } catch (err) {
    console.error("Failed to approve PO:", err);
    throw err;
  }
};

export const rejectPO = async (poId) => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/po/${poId}/reject`);
    return res.data;
  } catch (err) {
    console.error("Failed to reject PO:", err);
    throw err;
  }
};

export const sendChatMessage = async (message) => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/chat`, { message });
    return res.data;
  } catch (err) {
    console.error("Failed to send chat message:", err);
    throw err;
  }
};

export const startVoiceSession = async () => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/voice/agent/start`);
    return res.data;
  } catch (err) {
    console.error("Failed to start voice session:", err);
    return { status: "simulated", token: "mock_token" };
  }
};
