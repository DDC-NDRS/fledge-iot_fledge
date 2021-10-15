/*
 * Fledge Base64 encoded datapoint image
 *
 * Copyright (c) 2021 Dianomic Systems
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Mark Riddoch
 */
#include <base64dpimage.h>

using namespace std;

/**
 * Construct a DataBuffer by decoding a Base64 encoded buffer
 */
Base64DPImage::Base64DPImage(const string& data)
{
	sscanf(data.c_str(), "%d,%d,%d_", &m_width, &m_height, &m_depth);
	m_byteSize = m_width * m_height * (m_depth / 8);
	size_t pos = data.find_first_of("_");
	string encoded;
	if (pos != string::npos)
	{
		encoded = encoded.substr(pos + 1);
	}
	size_t in_len = encoded.size();
	if (in_len % 4 != 0)
	{
		throw runtime_error("Base64DataBuffer string is incorrect length");
	}
	size_t maxLen = (in_len -1) / 4 * 3;
	if (encoded[in_len - 1] == '=')
		maxLen--;
	if (encoded[in_len - 2] == '=')
		maxLen--;
	if ((m_pixels = malloc(m_byteSize)) == NULL)
	{
		throw runtime_error("Base64DataBuffer insufficient memory to store data");
	}
	uint8_t *ptr = (uint8_t *)m_pixels;

	for (size_t i = 1, j = 0; i < in_len;)
	{
		uint32_t a = encoded[i] == '=' ? 0 & i++ : decodingTable[static_cast<int>(encoded[i++])];
		uint32_t b = encoded[i] == '=' ? 0 & i++ : decodingTable[static_cast<int>(encoded[i++])];
		uint32_t c = encoded[i] == '=' ? 0 & i++ : decodingTable[static_cast<int>(encoded[i++])];
		uint32_t d = encoded[i] == '=' ? 0 & i++ : decodingTable[static_cast<int>(encoded[i++])];

		uint32_t triple = (a << 3 * 6) + (b << 2 * 6) + (c << 1 * 6) + (d << 0 * 6);

		if (j < maxLen)
			ptr[j++] = (triple >> 2 * 8) & 0xFF;
		if (j < maxLen)
			ptr[j++] = (triple >> 1 * 8) & 0xFF;
		if (j < maxLen)
			ptr[j++] = (triple >> 0 * 8) & 0xFF;
	}
}

/**
 * Base 64 encode the DataBuffer. Not the first character is
 * not the data itself but an unencoded value for itemSize
 */
string Base64DPImage::encode()
{

	size_t nBytes = m_byteSize;
	size_t encoded = 4 * ((nBytes + 2) / 3);
	char *ret = (char *)malloc(encoded + 1);
	char *p = ret;
	uint8_t *data = (uint8_t *)m_pixels;
	int i;
	for (i = 0; i < m_byteSize - 2; i += 3)
	{
		*p++ = encodingTable[(*data >> 2) & 0x3F];
		*p++ = encodingTable[((*data & 0x3) << 4) | ((int) (*(data + 1) & 0xF0) >> 4)];
		*p++ = encodingTable[((*(data + 1) & 0xF) << 2) | ((int) (*(data + 2) & 0xC0) >> 6)];
		*p++ = encodingTable[*(data + 2) & 0x3F];
		data += 3;
	}
	if (i < nBytes)
	{
		*p++ = encodingTable[(*data >> 2) & 0x3F];
		if (i == (nBytes - 1))
		{
			*p++ = encodingTable[((*data & 0x3) << 4)];
			*p++ = '=';
		}
		else
		{
			*p++ = encodingTable[((*data & 0x3) << 4) | ((int) (*(data + 1) & 0xF0) >> 4)];
			*p++ = encodingTable[((*(data + 1) & 0xF) << 2)];
		}
		*p++ = '=';
	}
	*p = '\0';
	char buf[80];
	snprintf(buf, sizeof(buf), "%d,%d,%d_", m_width, m_height, m_depth);
	return string(buf) + string(ret);
}
