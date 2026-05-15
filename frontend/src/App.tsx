// import AuthCallback from "./components/auth/AuthCallback";

import {
  Routes,
  Route,
} from "react-router-dom";

import Home from "./pages/Home";

function App() {
  return (
    <Routes>
      {/* Home */}
      <Route
        path="/"
        element={<Home />}
      />

      {/* Chat History Route */}
      <Route
        path="/chats/history/:sessionId"
        element={<Home />}
      />
    </Routes>
  );
}

export default App;