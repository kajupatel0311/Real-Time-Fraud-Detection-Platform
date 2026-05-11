import React, { useState } from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, Text, StatusBar } from 'react-native';
import DashboardScreen from './screens/DashboardScreen';
import ChatScreen from './screens/ChatScreen';
import AlertsScreen from './screens/AlertsScreen';
import HistoryScreen from './screens/HistoryScreen';
import { Theme } from './styles/theme';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return <DashboardScreen />;
      case 'chat': return <ChatScreen />;
      case 'alerts': return <AlertsScreen />;
      case 'history': return <HistoryScreen />;
      default: return <DashboardScreen />;
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.content}>
        {renderContent()}
      </View>

      <View style={styles.tabBar}>
        <TouchableOpacity 
          style={styles.tabItem} 
          onPress={() => setActiveTab('dashboard')}
        >
          <Text style={[styles.tabText, activeTab === 'dashboard' && styles.tabActive]}>Stats</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.tabItem} 
          onPress={() => setActiveTab('history')}
        >
          <Text style={[styles.tabText, activeTab === 'history' && styles.tabActive]}>History</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.tabItem} 
          onPress={() => setActiveTab('chat')}
        >
          <View style={styles.chatFab}>
            <Text style={styles.chatFabText}>Analyze</Text>
          </View>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.tabItem} 
          onPress={() => setActiveTab('alerts')}
        >
          <Text style={[styles.tabText, activeTab === 'alerts' && styles.tabActive]}>Alerts</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { flex: 1 },
  tabBar: { 
    flexDirection: 'row', 
    height: 60, 
    borderTopWidth: 1, 
    borderTopColor: Theme.colors.border, 
    backgroundColor: '#fff',
    alignItems: 'center'
  },
  tabItem: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  tabText: { fontSize: 12, color: Theme.colors.textMuted, fontWeight: '600' },
  tabActive: { color: Theme.colors.accent },
  chatFab: { 
    backgroundColor: Theme.colors.primary, 
    paddingHorizontal: 16, 
    paddingVertical: 8, 
    borderRadius: 20,
    marginTop: -30,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 5,
    elevation: 5
  },
  chatFabText: { color: '#fff', fontWeight: '700', fontSize: 12 }
});
