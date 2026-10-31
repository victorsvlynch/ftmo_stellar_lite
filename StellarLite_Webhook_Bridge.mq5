//+------------------------------------------------------------------+
//|                                   StellarLite_Webhook_Bridge.mq5 |
//|              FundedNext Stellar Lite ($5,000) - Webhook Bridge EA |
//|          Conecta MetaTrader 5 con el Motor Cuantitativo 24/7 OCI |
//+------------------------------------------------------------------+
#property copyright   "FundedNext Stellar Lite Quantitative Engine"
#property link        "https://github.com/victorsvlynch/ftmo_stellar_lite"
#property version     "2.00"
#property description "Expert Advisor de Enlace Webhook con el Bot de Python en Oracle Cloud VPS (157.137.225.144:8000)."
#property description "Recibe senales institucionales de NY_OPEN (Oro / XAUUSD) y ejecuta ordenes con SL, TP y Break-Even."

#include <Trade\Trade.mqh>

//--- Parametros de Entrada
input group "--- Servidor Oracle Cloud VPS ---"
input string InpServerUrl       = "http://127.0.0.1:8000";       // URL Webhook (127.0.0.1:8000 o 157.137.225.144:8000)
input int    InpPollIntervalSec = 1;                              // Frecuencia de Sondeo (segundos)

input group "--- Configuracion de Trading Institucional ---"
input ulong  InpMagicNumber     = 505001;                         // Magic Number Institucional
input ulong  InpDeviationPoints = 30;                             // Slippage Maximo Permitido (puntos)
input string InpPreferredSymbol = "XAUUSD";                       // Simbolo Preferido (o vacio para usar el grafico)

//--- Instancias Globales
CTrade         ExtTrade;
datetime       ExtLastPollTime = 0;
string         ExtServerStatus = "DESCONECTADO";
string         ExtLastActionMsg = "Esperando primera conexion...";
int            ExtConsecutiveErrors = 0;

//+------------------------------------------------------------------+
//| Helper: Extraer valor de string de un JSON plano                 |
//+------------------------------------------------------------------+
string JsonExtractString(const string json, const string key)
{
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(json, searchKey);
   if(pos < 0) return "";
   
   int start = pos + StringLen(searchKey);
   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '\"'))
      start++;
      
   int end = start;
   while(end < StringLen(json) && StringGetCharacter(json, end) != '\"' && StringGetCharacter(json, end) != ',' && StringGetCharacter(json, end) != '}')
      end++;
      
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Helper: Extraer valor numerico o booleano de un JSON plano       |
//+------------------------------------------------------------------+
double JsonExtractDouble(const string json, const string key)
{
   string val = JsonExtractString(json, key);
   return StringToDouble(val);
}

bool JsonExtractBool(const string json, const string key)
{
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(json, searchKey);
   if(pos < 0) return false;
   int start = pos + StringLen(searchKey);
   string sub = StringSubstr(json, start, 10);
   StringToLower(sub);
   return (StringFind(sub, "true") >= 0);
}

//+------------------------------------------------------------------+
//| Resolver simbolo real del broker (Oro, EUR/USD, S&P 500, etc.)   |
//+------------------------------------------------------------------+
string ResolveBrokerSymbol(const string requestedSymbol)
{
   if(SymbolInfoDouble(requestedSymbol, SYMBOL_BID) > 0)
      return requestedSymbol;
      
   string clean = requestedSymbol;
   StringToUpper(clean);
   StringReplace(clean, "=X", "");
   StringReplace(clean, "=F", "");
   StringReplace(clean, "/", "");

   // A. S&P 500
   if(StringFind(clean, "500") >= 0 || StringFind(clean, "SPX") >= 0 || StringFind(clean, "ES") >= 0)
   {
      string candidates[] = {"US500", "US500.cash", "SPX500", "USA500", "US500m", "US500.raw", "US500.pro", "SP500", "ES"};
      for(int i = 0; i < ArraySize(candidates); i++)
         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];
   }
   // B. EUR/USD
   else if(StringFind(clean, "EUR") >= 0)
   {
      string candidates[] = {"EURUSD", "EURUSDm", "EURUSD.raw", "EURUSD.pro", "EURUSDb", "EURUSD.cash", "EURUSD+"};
      for(int i = 0; i < ArraySize(candidates); i++)
         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];
   }
   // C. Nasdaq 100
   else if(StringFind(clean, "100") >= 0 || StringFind(clean, "NAS") >= 0 || StringFind(clean, "USTEC") >= 0 || StringFind(clean, "NQ") >= 0)
   {
      string candidates[] = {"US100", "US100.cash", "NAS100", "USTEC", "US100m", "US100.raw", "NAS100.raw", "NQ"};
      for(int i = 0; i < ArraySize(candidates); i++)
         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];
   }
   // D. Oro / XAUUSD
   else
   {
      string candidates[] = {"XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.raw", "XAUUSD.pro", "XAUUSDb"};
      for(int i = 0; i < ArraySize(candidates); i++)
         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];
   }

   // Busqueda inteligente en la lista completa de simbolos del broker
   int total = SymbolsTotal(false);
   for(int i = 0; i < total; i++)
   {
      string sName = SymbolName(i, false);
      string sUpper = sName;
      StringToUpper(sUpper);
      if(StringFind(clean, "500") >= 0 && (StringFind(sUpper, "500") >= 0 || StringFind(sUpper, "SPX") >= 0))
         return sName;
      if(StringFind(clean, "EUR") >= 0 && StringFind(sUpper, "EUR") >= 0 && StringFind(sUpper, "USD") >= 0)
         return sName;
      if(StringFind(clean, "100") >= 0 && (StringFind(sUpper, "100") >= 0 || StringFind(sUpper, "NAS") >= 0))
         return sName;
      if((StringFind(clean, "XAU") >= 0 || StringFind(clean, "GC") >= 0) && (StringFind(sUpper, "XAU") >= 0 || StringFind(sUpper, "GOLD") >= 0))
         return sName;
   }

   return _Symbol;
}

//+------------------------------------------------------------------+
//| Realizar peticion HTTP WebRequest                                |
//+------------------------------------------------------------------+
bool SendHttpRequest(const string method, const string url, const string postData, string &responseOut, int &statusCodeOut)
{
   char postDataArr[];
   char resultArr[];
   string headers = "Content-Type: application/json\r\n";
   string resultHeaders;
   
   if(StringLen(postData) > 0)
      StringToCharArray(postData, postDataArr, 0, StringLen(postData));
   else
      ArrayResize(postDataArr, 0);
      
   ResetLastError();
   int res = WebRequest(
      method,
      url,
      headers,
      3000,
      postDataArr,
      resultArr,
      resultHeaders
   );
   
   statusCodeOut = res;
   if(res == 200)
   {
      responseOut = CharArrayToString(resultArr);
      return true;
   }
   
   int err = GetLastError();
   if(err == 4014) // ERR_WEBREQUEST_NOT_ALLOWED
   {
      PrintFormat("[ERROR FATAL] WebRequest no permitido para la URL '%s'. Agregala en Herramientas -> Opciones -> Asesores Expertos.", InpServerUrl);
      ExtServerStatus = "ERROR: URL NO AUTORIZADA EN MT5 (Herramientas -> Opciones -> Asesores Expertos)";
   }
   else
   {
      PrintFormat("[WEB] WebRequest fallo (Cod: %d, Error: %d)", res, err);
   }
   return false;
}

//+------------------------------------------------------------------+
//| Confirmar accion completada hacia Oracle Cloud                   |
//+------------------------------------------------------------------+
void ConfirmActionToCloud(int actionId, ulong ticket, double price, bool success)
{
   string confirmUrl = InpServerUrl + "/api/confirm";
   string payload = StringFormat(
      "{\"action_id\":%d,\"ticket\":%I64u,\"price\":%.5f,\"success\":%s}",
      actionId, ticket, price, success ? "true" : "false"
   );
   string resp;
   int status;
   SendHttpRequest("POST", confirmUrl, payload, resp, status);
}

//+------------------------------------------------------------------+
//| Actualizar tablero visual en el grafico                          |
//+------------------------------------------------------------------+
void UpdateChartDashboard()
{
   string sep = "========================================================================\n";
   string text = "";
   text += sep;
   text += "  FUNDEDNEXT STELLAR LITE ($5,000) -- WEBHOOK BRIDGE EA MT5\n";
   text += "  Estrategia Ganadora: NY_OPEN (Oro / XAUUSD) | R:R 1:2 + Break-Even\n";
   text += sep;
   text += StringFormat("  Servidor Oracle VPS: %s\n", InpServerUrl);
   text += StringFormat("  Estado Conexion    : %s\n", ExtServerStatus);
   text += StringFormat("  Ultimo Sondeo      : %s (Cada %d seg)\n", TimeToString(TimeCurrent(), TIME_MINUTES|TIME_SECONDS), InpPollIntervalSec);
   text += StringFormat("  Magic Number       : %I64u | Slippage: %I64u pts\n", InpMagicNumber, InpDeviationPoints);
   text += StringFormat("  Simbolo Operado    : %s\n", ResolveBrokerSymbol(InpPreferredSymbol));
   text += sep;
   text += StringFormat("  Ultima Accion      : %s\n", ExtLastActionMsg);
   text += sep;
   text += "  >> Monitoreo 24/7 Activo | Sincronizado con Python en Oracle Cloud <<\n";
   Comment(text);
}

//+------------------------------------------------------------------+
//| Procesar accion recibida desde Oracle Cloud                      |
//+------------------------------------------------------------------+
void ProcessCloudAction(const string json)
{
   int actionId = (int)JsonExtractDouble(json, "action_id");
   string action = JsonExtractString(json, "action");
   string symReq = JsonExtractString(json, "symbol");
   double lots = JsonExtractDouble(json, "lots");
   double price = JsonExtractDouble(json, "price");
   double sl = JsonExtractDouble(json, "sl");
   double tp = JsonExtractDouble(json, "tp");
   int tradeId = (int)JsonExtractDouble(json, "trade_id");
   string comment = JsonExtractString(json, "comment");
   if(StringLen(comment) == 0) comment = "FundedNext NY_ORB";
   
   string realSymbol = ResolveBrokerSymbol(symReq);
   
   // A. APERTURA DE COMPRA (BUY)
   if(action == "OPEN_BUY")
   {
      // Verificar si ya tenemos posicion abierta en este simbolo con ese magic
      bool alreadyOpen = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == realSymbol)
         {
            alreadyOpen = true;
            break;
         }
      }
      
      if(!alreadyOpen)
      {
         MqlTick tick;
         if(!SymbolInfoTick(realSymbol, tick))
         {
            ExtLastActionMsg = "Error: SymbolInfoTick fallo para " + realSymbol;
            ConfirmActionToCloud(actionId, 0, 0.0, false);
            return;
         }

         double askPrice = tick.ask;
         int digits = (int)SymbolInfoInteger(realSymbol, SYMBOL_DIGITS);

         // Calcular distancias institucionales (R:R 1:2) relativas al precio de ejecucion
         double slDist = (sl > 0 && price > 0) ? MathAbs(price - sl) : 0.0;
         double tpDist = (tp > 0 && price > 0) ? MathAbs(price - tp) : 0.0;
         if(slDist <= 0.0)
         {
            if(digits >= 4) slDist = 250 * SymbolInfoDouble(realSymbol, SYMBOL_POINT); // ~25 pips en Forex
            else if(askPrice > 1000) slDist = (StringFind(realSymbol, "XAU") >= 0 || StringFind(realSymbol, "GOLD") >= 0) ? 6.50 : 15.0; // Oro o Indices
            else slDist = 50 * SymbolInfoDouble(realSymbol, SYMBOL_POINT);
         }
         if(tpDist <= 0.0) tpDist = slDist * 2.0;

         // Detectar si la cotizacion del broker difiere de la fuente externa por escala de contrato
         bool priceScaleMismatch = (price > 0 && (MathAbs(askPrice - price) / askPrice) > 0.02);

         double slPrice, tpPrice;
         if(priceScaleMismatch || sl <= 0 || sl >= askPrice)
            slPrice = NormalizeDouble(askPrice - slDist, digits);
         else
            slPrice = NormalizeDouble(sl, digits);

         if(priceScaleMismatch || tp <= 0 || tp <= askPrice)
            tpPrice = NormalizeDouble(askPrice + tpDist, digits);
         else
            tpPrice = NormalizeDouble(tp, digits);

         PrintFormat("[EA MT5] Ejecutando COMPRA institucional: %s %.2f lotes @ %.2f | SL: %.2f | TP: %.2f (Dist SL: %.2f, TP: %.2f)", 
                     realSymbol, lots, askPrice, slPrice, tpPrice, slDist, tpDist);

         bool orderSuccess = false;
         ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};
         for(int f = 0; f < ArraySize(fillModes); f++)
         {
            ExtTrade.SetTypeFilling(fillModes[f]);
            if(ExtTrade.Buy(lots, realSymbol, askPrice, slPrice, tpPrice, comment))
            {
               orderSuccess = true;
               break;
            }
         }

         // Fallback para brokers con Market Execution (donde SL/TP no pueden enviarse en la orden directa)
         if(!orderSuccess)
         {
            for(int f = 0; f < ArraySize(fillModes); f++)
            {
               ExtTrade.SetTypeFilling(fillModes[f]);
               if(ExtTrade.Buy(lots, realSymbol, askPrice, 0.0, 0.0, comment))
               {
                  orderSuccess = true;
                  ulong ordTicket = ExtTrade.ResultOrder();
                  Sleep(150);
                  ExtTrade.PositionModify(ordTicket, slPrice, tpPrice);
                  PrintFormat("[EA MT5] [MARKET EXECUTION] SL y TP aplicados via PositionModify -> Ticket #%I64u", ordTicket);
                  break;
               }
            }
         }

         if(orderSuccess)
         {
            ulong orderTicket = ExtTrade.ResultOrder();
            double fillPrice = ExtTrade.ResultPrice();
            ExtLastActionMsg = StringFormat("BUY #%I64u (%.2f Lotes) ejecutada @ %.2f", orderTicket, lots, fillPrice);
            PrintFormat("[EA MT5] [EXITO] Orden BUY colocada -> Ticket: #%I64u", orderTicket);
            ConfirmActionToCloud(actionId, orderTicket, fillPrice, true);
         }
         else
         {
            int err = GetLastError();
            ExtLastActionMsg = StringFormat("Error al abrir BUY: %d - %s", err, ExtTrade.ResultComment());
            PrintFormat("[EA MT5] [FALLO] No se pudo abrir BUY: %d - %s", err, ExtTrade.ResultComment());
            ConfirmActionToCloud(actionId, 0, 0.0, false);
         }
      }
      else
      {
         PrintFormat("[EA MT5] Posicion con Magic %I64u ya existe. Omitiendo duplicado.", InpMagicNumber);
         ConfirmActionToCloud(actionId, 0, 0.0, true);
      }
   }
   
   // B. APERTURA DE VENTA (SELL)
   else if(action == "OPEN_SELL")
   {
      bool alreadyOpen = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == realSymbol)
         {
            alreadyOpen = true;
            break;
         }
      }
      
      if(!alreadyOpen)
      {
         MqlTick tick;
         if(!SymbolInfoTick(realSymbol, tick))
         {
            ExtLastActionMsg = "Error: SymbolInfoTick fallo para " + realSymbol;
            ConfirmActionToCloud(actionId, 0, 0.0, false);
            return;
         }

         double bidPrice = tick.bid;
         int digits = (int)SymbolInfoInteger(realSymbol, SYMBOL_DIGITS);

         // Calcular distancias institucionales (R:R 1:2) relativas al precio de ejecucion
         double slDist = (sl > 0 && price > 0) ? MathAbs(sl - price) : 0.0;
         double tpDist = (tp > 0 && price > 0) ? MathAbs(price - tp) : 0.0;
         if(slDist <= 0.0)
         {
            if(digits >= 4) slDist = 250 * SymbolInfoDouble(realSymbol, SYMBOL_POINT); // ~25 pips en Forex
            else if(bidPrice > 1000) slDist = (StringFind(realSymbol, "XAU") >= 0 || StringFind(realSymbol, "GOLD") >= 0) ? 6.50 : 15.0; // Oro o Indices
            else slDist = 50 * SymbolInfoDouble(realSymbol, SYMBOL_POINT);
         }
         if(tpDist <= 0.0) tpDist = slDist * 2.0;

         // Detectar si la cotizacion del broker difiere de la fuente externa por escala de contrato
         bool priceScaleMismatch = (price > 0 && (MathAbs(bidPrice - price) / bidPrice) > 0.02);

         double slPrice, tpPrice;
         if(priceScaleMismatch || sl <= 0 || sl <= bidPrice)
            slPrice = NormalizeDouble(bidPrice + slDist, digits);
         else
            slPrice = NormalizeDouble(sl, digits);

         if(priceScaleMismatch || tp <= 0 || tp >= bidPrice)
            tpPrice = NormalizeDouble(bidPrice - tpDist, digits);
         else
            tpPrice = NormalizeDouble(tp, digits);

         PrintFormat("[EA MT5] Ejecutando VENTA institucional: %s %.2f lotes @ %.2f | SL: %.2f | TP: %.2f (Dist SL: %.2f, TP: %.2f)", 
                     realSymbol, lots, bidPrice, slPrice, tpPrice, slDist, tpDist);

         bool orderSuccess = false;
         ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};
         for(int f = 0; f < ArraySize(fillModes); f++)
         {
            ExtTrade.SetTypeFilling(fillModes[f]);
            if(ExtTrade.Sell(lots, realSymbol, bidPrice, slPrice, tpPrice, comment))
            {
               orderSuccess = true;
               break;
            }
         }

         // Fallback para brokers con Market Execution (donde SL/TP no pueden enviarse en la orden directa)
         if(!orderSuccess)
         {
            for(int f = 0; f < ArraySize(fillModes); f++)
            {
               ExtTrade.SetTypeFilling(fillModes[f]);
               if(ExtTrade.Sell(lots, realSymbol, bidPrice, 0.0, 0.0, comment))
               {
                  orderSuccess = true;
                  ulong ordTicket = ExtTrade.ResultOrder();
                  Sleep(150);
                  ExtTrade.PositionModify(ordTicket, slPrice, tpPrice);
                  PrintFormat("[EA MT5] [MARKET EXECUTION] SL y TP aplicados via PositionModify -> Ticket #%I64u", ordTicket);
                  break;
               }
            }
         }

         if(orderSuccess)
         {
            ulong orderTicket = ExtTrade.ResultOrder();
            double fillPrice = ExtTrade.ResultPrice();
            ExtLastActionMsg = StringFormat("SELL #%I64u (%.2f Lotes) ejecutada @ %.2f", orderTicket, lots, fillPrice);
            PrintFormat("[EA MT5] [EXITO] Orden SELL colocada -> Ticket: #%I64u", orderTicket);
            ConfirmActionToCloud(actionId, orderTicket, fillPrice, true);
         }
         else
         {
            int err = GetLastError();
            ExtLastActionMsg = StringFormat("Error al abrir SELL: %d - %s", err, ExtTrade.ResultComment());
            PrintFormat("[EA MT5] [FALLO] No se pudo abrir SELL: %d - %s", err, ExtTrade.ResultComment());
            ConfirmActionToCloud(actionId, 0, 0.0, false);
         }
      }
      else
      {
         ConfirmActionToCloud(actionId, 0, 0.0, true);
      }
   }
   
   // C. MODIFICACION DE STOP LOSS A BREAK-EVEN
   else if(action == "MODIFY_SL")
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            double curTp = PositionGetDouble(POSITION_TP);
            double entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            int digits = (int)SymbolInfoInteger(PositionGetString(POSITION_SYMBOL), SYMBOL_DIGITS);
            
            // Si es Break-Even o el precio de SL enviado difiere de la escala del broker,
            // fijar el SL exactamente al precio de apertura de la posición en MT5 (Riesgo = $0.00)
            bool isBe = (StringFind(comment, "Break-Even") >= 0 || StringFind(comment, "BREAK_EVEN") >= 0);
            double newSl = (isBe || (sl > 0 && MathAbs(entryPrice - sl) > 20.0)) ? NormalizeDouble(entryPrice, digits) : NormalizeDouble(sl, digits);

            PrintFormat("[EA MT5] Blindando posicion #%I64u con Break-Even: Nuevo SL: %.2f (Precio Entrada: %.2f)", ticket, newSl, entryPrice);
            if(ExtTrade.PositionModify(ticket, newSl, curTp))
            {
               ExtLastActionMsg = StringFormat("Posicion #%I64u blindada a Break-Even (SL: %.2f)", ticket, newSl);
               PrintFormat("[EA MT5] [EXITO] Posicion #%I64u modificada a Break-Even.", ticket);
               ConfirmActionToCloud(actionId, ticket, newSl, true);
            }
            else
            {
               PrintFormat("[EA MT5] [AVISO] Fallo al modificar SL a Break-Even: %s", ExtTrade.ResultComment());
            }
            break;
         }
      }
   }
   
   // D. CIERRE FORZOSO O DE FIN DE SEMANA (CLOSE)
   else if(action == "CLOSE_POSITION" || action == "CLOSE_ALL")
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            PrintFormat("[EA MT5] Cerrando posicion #%I64u a precio de mercado...", ticket);
            bool closedSuccess = false;
            ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};
            for(int f = 0; f < ArraySize(fillModes); f++)
            {
               ExtTrade.SetTypeFilling(fillModes[f]);
               if(ExtTrade.PositionClose(ticket, (ulong)InpDeviationPoints))
               {
                  closedSuccess = true;
                  break;
               }
            }

            if(closedSuccess)
            {
               ExtLastActionMsg = StringFormat("Posicion #%I64u cerrada a mercado.", ticket);
               PrintFormat("[EA MT5] [EXITO] Posicion #%I64u cerrada correctamente.", ticket);
               ConfirmActionToCloud(actionId, ticket, 0.0, true);
            }
            else
            {
               PrintFormat("[EA MT5] [FALLO] Error al cerrar posicion #%I64u: %s", ticket, ExtTrade.ResultComment());
               ConfirmActionToCloud(actionId, ticket, 0.0, false);
            }
            break;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("==================================================================");
   Print("  INICIANDO EXPERT ADVISOR: STELLARLITE WEBHOOK BRIDGE (MT5)     ");
   Print("  Modelo: FundedNext Stellar Lite ($5,000) | NY_OPEN (Oro)        ");
   Print("==================================================================");

   ExtTrade.SetExpertMagicNumber(InpMagicNumber);
   ExtTrade.SetDeviationInPoints(InpDeviationPoints);
   ExtTrade.SetTypeFillingBySymbol(ResolveBrokerSymbol(InpPreferredSymbol));

   // Comprobacion inicial de conectividad con Oracle Cloud
   string resp;
   int status;
   string healthUrl = InpServerUrl + "/api/health";
   
   if(SendHttpRequest("GET", healthUrl, "", resp, status))
   {
      ExtServerStatus = "CONECTADO A ORACLE CLOUD (ONLINE)";
      PrintFormat("[EA MT5] Conectado exitosamente con servidor Webhook: %s", resp);
   }
   else
   {
      ExtServerStatus = "CONECTANDO... (Revisa que la URL este autorizada en MT5)";
   }

   EventSetTimer(InpPollIntervalSec);
   UpdateChartDashboard();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
   Print("[EA MT5] Expert Advisor desinstalado del grafico.");
}

void CheckAutonomousStructuralTrailing()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         string sym = PositionGetString(POSITION_SYMBOL);
         ENUM_POSITION_TYPE pType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double curSl = PositionGetDouble(POSITION_SL);
         double curTp = PositionGetDouble(POSITION_TP);
         int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
         double pt = SymbolInfoDouble(sym, SYMBOL_POINT);

         MqlTick tick;
         if(!SymbolInfoTick(sym, tick)) continue;

         // Obtener distancia inicial 1R de riesgo
         double initialRiskDist = 0.0;
         if(curSl > 0.0)
            initialRiskDist = MathAbs(openPrice - curSl);
         if(initialRiskDist <= (5 * pt))
         {
            if(digits >= 4) initialRiskDist = 250 * pt;
            else if(openPrice > 1000) initialRiskDist = (StringFind(sym, "XAU") >= 0 || StringFind(sym, "GOLD") >= 0) ? 6.50 : 15.0;
            else initialRiskDist = 50 * pt;
         }

         // 1. Blindaje Break-Even a +1R (+1R de ganancia flotante alcanzado)
         if(pType == POSITION_TYPE_BUY)
         {
            if(tick.bid >= (openPrice + initialRiskDist) && (curSl < openPrice || curSl == 0.0))
            {
               double newSl = NormalizeDouble(openPrice, digits);
               PrintFormat("[EA MT5] [BREAK-EVEN AUTONOMO] Posicion BUY #%I64u alcanzo +1R (Dist: %.5f). Blindando SL a %.5f (Riesgo: $0.00)", 
                           ticket, initialRiskDist, newSl);
               if(ExtTrade.PositionModify(ticket, newSl, curTp))
               {
                  ExtLastActionMsg = StringFormat("BUY #%I64u blindada a Break-Even ($0.00 riesgo)", ticket);
                  curSl = newSl;
               }
            }
         }
         else if(pType == POSITION_TYPE_SELL)
         {
            if(tick.ask <= (openPrice - initialRiskDist) && (curSl > openPrice || curSl == 0.0))
            {
               double newSl = NormalizeDouble(openPrice, digits);
               PrintFormat("[EA MT5] [BREAK-EVEN AUTONOMO] Posicion SELL #%I64u alcanzo +1R (Dist: %.5f). Blindando SL a %.5f (Riesgo: $0.00)", 
                           ticket, initialRiskDist, newSl);
               if(ExtTrade.PositionModify(ticket, newSl, curTp))
               {
                  ExtLastActionMsg = StringFormat("SELL #%I64u blindada a Break-Even ($0.00 riesgo)", ticket);
                  curSl = newSl;
               }
            }
         }

         // 2. Trailing Stop por Estructura Tecnica M15
         // Se activa cuando la posicion avanza al menos +2R a favor
         double doubleRDist = initialRiskDist * 2.0;
         double buffer = MathMax(10.0 * pt, initialRiskDist * 0.15);
         double minSecuredGain = initialRiskDist * 0.50;

         MqlRates ratesM15[];
         ArraySetAsSeries(ratesM15, true);
         int copied = CopyRates(sym, PERIOD_M15, 1, 4, ratesM15);
         if(copied >= 4)
         {
            if(pType == POSITION_TYPE_SELL && (openPrice - tick.ask) >= doubleRDist)
            {
               // Buscar el maximo de las ultimas 4 velas M15 cerradas (resistencia)
               double maxHigh = ratesM15[0].high;
               for(int k = 1; k < copied; k++)
               {
                  if(ratesM15[k].high > maxHigh) maxHigh = ratesM15[k].high;
               }
               double structSl = NormalizeDouble(maxHigh + buffer, digits);
               // Si la estructura permite asegurar beneficio y es mas favorable que el SL actual
               if(structSl < openPrice && (curSl == 0.0 || structSl < curSl) && (openPrice - structSl) >= minSecuredGain)
               {
                  PrintFormat("[EA MT5] [TRAILING M15] SELL #%I64u: Nuevo SL Estructural @ %.5f (Max M15: %.5f + Buffer: %.5f). Ganancia bloqueada: +%.5f", 
                              ticket, structSl, maxHigh, buffer, (openPrice - structSl));
                  if(ExtTrade.PositionModify(ticket, structSl, curTp))
                  {
                     ExtLastActionMsg = StringFormat("SELL #%I64u Trailing M15 activo @ %.5f (+%.5f garantizados)", ticket, structSl, (openPrice - structSl));
                  }
               }
            }
            else if(pType == POSITION_TYPE_BUY && (tick.bid - openPrice) >= doubleRDist)
            {
               // Buscar el minimo de las ultimas 4 velas M15 cerradas (soporte)
               double minLow = ratesM15[0].low;
               for(int k = 1; k < copied; k++)
               {
                  if(ratesM15[k].low < minLow) minLow = ratesM15[k].low;
               }
               double structSl = NormalizeDouble(minLow - buffer, digits);
               if(structSl > openPrice && (curSl == 0.0 || structSl > curSl) && (structSl - openPrice) >= minSecuredGain)
               {
                  PrintFormat("[EA MT5] [TRAILING M15] BUY #%I64u: Nuevo SL Estructural @ %.5f (Min M15: %.5f - Buffer: %.5f). Ganancia bloqueada: +%.5f", 
                              ticket, structSl, minLow, buffer, (structSl - openPrice));
                  if(ExtTrade.PositionModify(ticket, structSl, curTp))
                  {
                     ExtLastActionMsg = StringFormat("BUY #%I64u Trailing M15 activo @ %.5f (+%.5f garantizados)", ticket, structSl, (structSl - openPrice));
                  }
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert timer function (Polling continuo al Servidor Webhook)     |
//+------------------------------------------------------------------+
void OnTimer()
{
   ExtLastPollTime = TimeCurrent();
   string signalUrl = InpServerUrl + "/api/signal";
   string resp;
   int status;
   
   if(SendHttpRequest("GET", signalUrl, "", resp, status))
   {
      ExtConsecutiveErrors = 0;
      ExtServerStatus = "CONECTADO A ORACLE CLOUD (ONLINE)";
      
      bool hasAction = JsonExtractBool(resp, "has_action");
      if(hasAction)
      {
         ProcessCloudAction(resp);
      }
      else
      {
         // Auto-Sincronización de Seguridad:
         // Si la nube indica que NO hay operaciones abiertas en el bot (open_trades_count == 0),
         // y en MT5 existe una posición con nuestro Magic Number que lleva abierta más de 15 segundos,
         // significa que el bot ya cerró la posición por TP, SL o cierre de sesión en la nube.
         double openTradesCloud = JsonExtractDouble(resp, "open_trades_count");
         if(openTradesCloud == 0)
         {
            for(int i = PositionsTotal() - 1; i >= 0; i--)
            {
               ulong ticket = PositionGetTicket(i);
               if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
               {
                  datetime posTime = (datetime)PositionGetInteger(POSITION_TIME);
                  if(TimeCurrent() - posTime > 15)
                  {
                     PrintFormat("[EA MT5] [AUTO-SYNC] Nube sin operaciones (open_trades_count = 0). Sincronizando cierre de posicion #%I64u...", ticket);
                     ENUM_ORDER_TYPE_FILLING fillModes[] = {ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN};
                     bool closedOk = false;
                     for(int f = 0; f < ArraySize(fillModes); f++)
                     {
                        ExtTrade.SetTypeFilling(fillModes[f]);
                        if(ExtTrade.PositionClose(ticket, (ulong)InpDeviationPoints))
                        {
                           closedOk = true;
                           break;
                        }
                     }
                     if(closedOk)
                     {
                        ExtLastActionMsg = StringFormat("Posicion #%I64u auto-sincronizada y cerrada.", ticket);
                        PrintFormat("[EA MT5] [AUTO-SYNC] Posicion #%I64u cerrada con exito.", ticket);
                     }
                  }
               }
            }
         }
      }
   }
   else
   {
      ExtConsecutiveErrors++;
      if(ExtConsecutiveErrors >= 5)
      {
         ExtServerStatus = StringFormat("FALLO DE CONEXION (%d reintentos fallidos)", ExtConsecutiveErrors);
      }
   }

   // Guardia de blindaje autónomo Break-Even local y Trailing Stop M15
   CheckAutonomousStructuralTrailing();
   
   UpdateChartDashboard();
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // El sondeo principal se ejecuta en OnTimer para no sobrecargar el servidor
}
//+------------------------------------------------------------------+
