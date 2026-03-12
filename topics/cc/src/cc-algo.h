#ifndef TCP_AUTO_CC_H
#define TCP_AUTO_CC_H

#include "ns3/nstime.h"
#include "ns3/tcp-congestion-ops.h"
#include "ns3/tcp-socket-state.h"

namespace ns3 {

class TcpAutoCC : public TcpCongestionOps {
public:
    static TypeId GetTypeId();

    TcpAutoCC();
    TcpAutoCC(const TcpAutoCC& sock);
    ~TcpAutoCC() override = default;

    std::string GetName() const override;
    uint32_t GetSsThresh(Ptr<const TcpSocketState> tcb, uint32_t bytesInFlight) override;
    void IncreaseWindow(Ptr<TcpSocketState> tcb, uint32_t segmentsAcked) override;
    void PktsAcked(Ptr<TcpSocketState> tcb, uint32_t segmentsAcked, const Time& rtt) override;
    Ptr<TcpCongestionOps> Fork() override;

private:
    Time m_baseRtt; // minimum RTT observed (true propagation delay proxy)
};

} // namespace ns3

#endif // TCP_AUTO_CC_H
