/* SPDX-License-Identifier: BSD-2-Clause-Patent
 *
 * SPDX-FileCopyrightText: 2019-2020 the prplMesh contributors (see AUTHORS.md)
 *
 * This code is subject to the terms of the BSD+Patent license.
 * See LICENSE file for more details.
 */

#ifndef MAPFUTILS_H_
#define MAPFUTILS_H_

#include <string>

namespace mapf {

/**
 * @brief mapf utility functions
 */
namespace utils {

/**
 * @brief dump buffer in hex mode
 * 
 * Debugging utility to get a string representation of a given
 * buffer in hexadecimal, split to bytes.
 * 
 * @param buffer input buffer
 * @param len input buffer length
 * @return std::string string containing the hexadecimal buffer contets
 */
std::string dump_buffer(uint8_t *buffer, size_t len);


/**
 * @brief a bytes buffer
 *
 * This class represents a collection of opaque bytes.
 */
class bytes : public std::basic_string<uint8_t> {
public:
    bytes()
        : std::basic_string<uint8_t>()
    {}

    bytes(const uint8_t* buf, size_t buf_size)
        : std::basic_string<uint8_t>(buf, buf_size)
    {}
};

} // namespace utils
} // namespace mapf
#endif // MAPFUTILS_H_
