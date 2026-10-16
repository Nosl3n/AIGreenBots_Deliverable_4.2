/*
 * common/vegetation/plant_discs.h — the plants vegetation_concept publishes, read as discs. SHARED, header-only.
 *
 * vegetation_concept owns one `plant_*` node per plant it has recognised (ADE20K vegetation masks from retina):
 * the canopy seen from above. trunk_concept owns one `trunk_*` node per trunk (ZED + LiDAR): the space a trunk
 * forbids. Both carry a world→node RT at the centre, obj_width_m = the disc diameter and height_m = its top.
 * Every consumer reads them THE SAME WAY, here:
 *   * controller        — a disc to plan around and draw, like a person;
 *   * residual_concept  — the space a plant explains, so its returns stop being "unexplained" occupancy;
 *   * human_concept     — space that is already taken: no person is born inside a plant, and a LiDAR return
 *                         inside a plant belongs to the plant, not to a person standing next to it.
 *
 * PlantIndex answers "which plant is this point in?" in O(1) for per-point use (a LiDAR sweep is ~20k points
 * at ~17 Hz; testing each against every plant would cost far more than the question is worth).
 */
#pragma once

#include <cmath>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include <Eigen/Dense>
#include <dsr/api/dsr_api.h>
#include <dsr/api/dsr_inner_eigen_api.h>

namespace rc::veg
{

struct PlantDisc
{
    std::string name;
    Eigen::Vector2f c = Eigen::Vector2f::Zero();   // centre, world frame (m)
    float r = 0.0f;                                 // radius seen from above (m)
    float h = 0.0f;                                 // top above the ground (m); 0 = unknown

    [[nodiscard]] bool contains(const Eigen::Vector2f& p) const { return (p - c).squaredNorm() <= r * r; }
};

// Two agents publish `plant` nodes, told apart by name (each owns its own; if it is not running, none exist):
//   trunk_*  trunk_concept      — a TRUNK and the space it forbids (R from its node): an obstacle;
//   plant_*  vegetation_concept — FOLIAGE seen from above: what can hide things, not an obstacle by itself.
inline constexpr std::string_view kTrunkPrefix   = "trunk_";
inline constexpr std::string_view kFoliagePrefix = "plant_";

// Every `plant` node with a resolvable world→plant transform and a positive width; `prefix` = only those
// whose name starts with it (empty = all of them).
// ★THE RT EDGE IS READ DIRECTLY, NOT THROUGH inner_eigen.transform(). Every plant hangs from the world frame,
// so world->plant IS that one edge — but transform() walks the tree with get_node() copies, and the world
// node it copies carries an RT edge (with its history ring) to EVERY plant and person. Its ts==0 cache does
// not help: any edge under the world frame changing (the robot's, at the localiser rate) invalidates it.
// Measured in the controller with 62 trunks: 48 ms a cycle this way, which alone kept the control loop below
// the LiDAR rate. get_edge(from, to) copies only the one edge. A plant parented elsewhere still resolves
// through the tree.
inline std::vector<PlantDisc> read_plant_discs(DSR::DSRGraph& G, DSR::InnerEigenAPI& inner_eigen,
                                               const std::string& world_frame, std::string_view prefix = {})
{
    std::vector<PlantDisc> out;
    const auto world_id = G.get_id_from_name(world_frame);
    const auto rt = G.get_rt_api();
    for (const auto& n : G.get_nodes_by_type("plant"))
    {
        if (not n.name().starts_with(prefix))
            continue;
        const float h = G.get_attrib_by_name<height_m_att>(n).value_or(0.0f);
        const float w = G.get_attrib_by_name<obj_width_m_att>(n).value_or(0.0f);
        if (not (w > 0.0f))
            continue;
        std::optional<Eigen::Vector3d> t;
        if (world_id.has_value())
            if (const auto e = G.get_edge(world_id.value(), n.id(), "RT"); e.has_value())
                if (const auto m = rt->get_edge_RT_as_rtmat(e.value()); m.has_value())
                    t = m->translation();
        if (not t.has_value())
            t = inner_eigen.transform(world_frame, n.name(), 0);
        if (not t.has_value() or not t->allFinite())
            continue;
        PlantDisc d;
        d.name = n.name();
        d.c = Eigen::Vector2f(static_cast<float>(t->x()), static_cast<float>(t->y()));
        d.r = 0.5f * w;
        d.h = h;
        out.push_back(std::move(d));
    }
    return out;
}

// Spatial hash of the discs on a coarse grid: each disc is registered in every cell its bounding square touches,
// so a lookup checks only the handful of discs near the point.
class PlantIndex
{
public:
    PlantIndex() = default;
    explicit PlantIndex(std::vector<PlantDisc> discs, float cell_m = 1.0f) : discs_(std::move(discs)), cell_(cell_m)
    {
        for (std::size_t i = 0; i < discs_.size(); ++i)
        {
            const auto& d = discs_[i];
            for (int ix = cell(d.c.x() - d.r); ix <= cell(d.c.x() + d.r); ++ix)
                for (int iy = cell(d.c.y() - d.r); iy <= cell(d.c.y() + d.r); ++iy)
                    buckets_[key(ix, iy)].push_back(i);
        }
    }

    [[nodiscard]] bool empty() const { return discs_.empty(); }
    [[nodiscard]] const std::vector<PlantDisc>& discs() const { return discs_; }

    // The plant whose disc contains p (the nearest centre if two overlap), or nullptr.
    [[nodiscard]] const PlantDisc* containing(const Eigen::Vector2f& p) const
    {
        if (discs_.empty())
            return nullptr;
        const auto it = buckets_.find(key(cell(p.x()), cell(p.y())));
        if (it == buckets_.end())
            return nullptr;
        const PlantDisc* best = nullptr;
        float best_d2 = 0.0f;
        for (const std::size_t i : it->second)
        {
            const float d2 = (p - discs_[i].c).squaredNorm();
            if (discs_[i].contains(p) and (best == nullptr or d2 < best_d2))
            {
                best = &discs_[i];
                best_d2 = d2;
            }
        }
        return best;
    }

private:
    std::vector<PlantDisc> discs_;
    float cell_ = 1.0f;
    std::unordered_map<std::int64_t, std::vector<std::size_t>> buckets_;

    [[nodiscard]] int cell(float v) const { return static_cast<int>(std::floor(v / cell_)); }
    static std::int64_t key(int ix, int iy)
    {
        return (static_cast<std::int64_t>(ix) << 32) ^ static_cast<std::int64_t>(static_cast<std::uint32_t>(iy));
    }
};

}  // namespace rc::veg
