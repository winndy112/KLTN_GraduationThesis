import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MainLayout } from './layout/AppShell';
import Home from './pages/Home';
import Sensors from './pages/Sensors';
import CTI from './pages/CTI';
import Rules from './pages/Rules';
import Alerts from './pages/Alerts';
import Logs from './pages/Logs';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Home />} />
            <Route path="sensors" element={<Sensors />} />
            <Route path="cti" element={<CTI />} />
            <Route path="rules" element={<Rules />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="logs" element={<Logs />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
