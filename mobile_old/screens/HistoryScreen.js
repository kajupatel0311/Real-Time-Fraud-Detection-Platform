import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, StyleSheet, ActivityIndicator, TextInput } from 'react-native';
import { Theme } from '../styles/theme';
import { api } from '../services/api';

export default function HistoryScreen() {
  const [history, setHistory] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const data = await api.fetchHistory(50);
      setHistory(data);
      setFiltered(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (text) => {
    setSearch(text);
    if (!text) {
      setFiltered(history);
      return;
    }
    const filteredData = history.filter(item => 
      item.transaction_id.toLowerCase().includes(text.toLowerCase()) ||
      item.risk_level.toLowerCase().includes(text.toLowerCase())
    );
    setFiltered(filteredData);
  };

  const renderItem = ({ item }) => (
    <View style={styles.txnCard}>
      <View style={styles.row}>
        <Text style={styles.txnId}>{item.transaction_id}</Text>
        <Text style={[styles.riskLabel, { color: Theme.colors[item.risk_level.toLowerCase()] }]}>
          {item.risk_level}
        </Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.amount}>₹{item.amount.toLocaleString()}</Text>
        <Text style={styles.time}>{item.timestamp.split('T')[1].split('Z')[0]}</Text>
      </View>
      <Text style={styles.action}>{item.action}</Text>
    </View>
  );

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color={Theme.colors.accent} /></View>;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Audit Trail</Text>
        <TextInput 
          style={styles.searchBar}
          placeholder="Search by ID or Risk..."
          value={search}
          onChangeText={handleSearch}
        />
      </View>

      <FlatList 
        data={filtered}
        renderItem={renderItem}
        keyExtractor={item => item.transaction_id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>No matching transactions found.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Theme.colors.background },
  header: { padding: 24, paddingTop: 40, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: Theme.colors.border },
  title: { fontSize: 24, fontWeight: '800', color: Theme.colors.textDark, marginBottom: 16 },
  searchBar: { backgroundColor: Theme.colors.background, padding: 12, borderRadius: 12, fontSize: 14, fontWeight: '500' },
  list: { padding: 16 },
  txnCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 12, borderWeight: 1, borderColor: Theme.colors.border },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  txnId: { fontSize: 13, fontFamily: 'monospace', fontWeight: '700', color: Theme.colors.textDark },
  riskLabel: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase' },
  amount: { fontSize: 18, fontWeight: '800', color: Theme.colors.textDark },
  time: { fontSize: 11, color: Theme.colors.textMuted, fontWeight: '600' },
  action: { fontSize: 12, color: Theme.colors.textMuted, fontWeight: '600', marginTop: 4 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { textAlign: 'center', marginTop: 40, color: Theme.colors.textMuted }
});
