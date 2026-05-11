import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, StyleSheet, ActivityIndicator } from 'react-native';
import { Theme } from '../styles/theme';
import { api } from '../services/api';

export default function AlertsScreen() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAlerts();
  }, []);

  const loadAlerts = async () => {
    try {
      const data = await api.fetchAlerts();
      setAlerts(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const renderAlert = ({ item }) => (
    <View style={styles.alertCard}>
      <View style={styles.alertHeader}>
        <Text style={styles.alertType}>Critical Alert</Text>
        <Text style={styles.alertTime}>{item.timestamp.split('T')[1].split('Z')[0]}</Text>
      </View>
      <Text style={styles.alertTitle}>₹{item.amount.toLocaleString()} - {item.transaction_id}</Text>
      <Text style={styles.alertReason}>{item.reasons[0]}</Text>
    </View>
  );

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color={Theme.colors.danger} /></View>;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>High Risk Alerts</Text>
        <Text style={styles.sub}>Critical transactions requiring review.</Text>
      </View>
      
      <FlatList 
        data={alerts}
        renderItem={renderAlert}
        keyExtractor={item => item.transaction_id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>No active critical alerts.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Theme.colors.background },
  header: { padding: 24, paddingTop: 40 },
  title: { fontSize: 24, fontWeight: '800', color: Theme.colors.textDark },
  sub: { fontSize: 13, color: Theme.colors.textMuted, marginTop: 4 },
  list: { padding: 16 },
  alertCard: { backgroundColor: '#fff', borderRadius: 16, padding: 20, marginBottom: 12, borderLeftWidth: 4, borderLeftColor: Theme.colors.danger, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 5, elevation: 2 },
  alertHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  alertType: { fontSize: 11, fontWeight: '800', color: Theme.colors.danger, textTransform: 'uppercase' },
  alertTime: { fontSize: 11, color: Theme.colors.textMuted, fontWeight: '600' },
  alertTitle: { fontSize: 16, fontWeight: '800', color: Theme.colors.textDark, marginBottom: 4 },
  alertReason: { fontSize: 13, color: Theme.colors.text, fontWeight: '500' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { textAlign: 'center', marginTop: 40, color: Theme.colors.textMuted }
});
